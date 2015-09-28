from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.template import loader
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from hashlib import md5
from datetime import date, datetime

from tasks.models import Task, Nag, Claim, CalendarSettings
from members.models import Member

from icalendar import Calendar, Event


def _get_task_and_nag(task_pk, auth_token):
    md5str = md5(auth_token.encode()).hexdigest()
    task = get_object_or_404(Task, pk=task_pk)
    nag = get_object_or_404(Nag, auth_token_md5=md5str)
    assert(task in nag.tasks.all())
    return task, nag


def offer_task(request, task_pk, auth_token):

    task, nag = _get_task_and_nag(task_pk, auth_token)

    if request.method == 'POST':
        hours = request.POST['hours']
        # TODO: There's some risk that user will end up here via browser history. Catch unique violoation exception?
        Claim.objects.create(task=task, member=nag.who, hours_claimed=hours, status=Claim.CURRENT)
        return redirect('task:offer-more-tasks', task_pk=task_pk, auth_token=auth_token)

    else:  # GET and other methods

        # TODO: Is task closed?
        # TODO: Is task fully claimed?
        # TODO: Is task scheduled in the past?
        # TODO: Is member still eligible to work the task?

        params = {
            "task": task,
            "member": nag.who,
            "dow": task.scheduled_weekday(),
            "claims": task.claim_set.filter(status=Claim.CURRENT),
            "max_hrs_to_claim": float(min(task.unclaimed_hours(), task.duration.seconds/3600.0)),
            "auth_token": auth_token
        }
        return render(request, 'tasks/offer_task.html', params)


def offer_more_tasks(request, task_pk, auth_token):

    task, nag = _get_task_and_nag(task_pk, auth_token)

    if request.method == 'POST':
        pks = request.POST.getlist('tasks')
        for pk in pks:
            t = Task.objects.get(pk=pk)
            # TODO: There's some risk that user will end up here via browser history. Catch unique violoation exception?
            Claim.objects.create(task=t, member=nag.who, hours_claimed=t.duration.seconds/3600.0, status=Claim.CURRENT)
        return redirect('task:offers-done', auth_token=auth_token)

    else: # GET or other methods:

        all_future_instances = Task.objects.filter(
            recurring_task_template=task.recurring_task_template,
            scheduled_date__gt=task.scheduled_date,
            work_done=False
        )
        future_instances_same_dow = []
        for instance in all_future_instances:
            if instance.scheduled_weekday() == task.scheduled_weekday() \
               and instance.unclaimed_hours() == instance.work_estimate \
               and nag.who in instance.all_eligible_claimants():
                future_instances_same_dow.append(instance)
            if len(future_instances_same_dow) > 3:  # Don't overwhelm potential worker.
                break

        if len(future_instances_same_dow) > 0:
            params = {
                "task": task,
                "member": nag.who,
                "dow": task.scheduled_weekday(),
                "instances": future_instances_same_dow,
                "auth_token": auth_token,
            }
            return render(request, 'tasks/offer_more_tasks.html', params)
        else:  # There aren't any future instances of interest so we're done"
            return redirect('task:offers-done', auth_token=auth_token)


"""
def offer_adjacent_tasks(request, auth_token):

    md5str = md5(auth_token.encode()).hexdigest()
    nag = get_object_or_404(Nag, auth_token_md5=md5str)
    member = nag.who

    if request.method == 'POST':
        pks = request.POST.getlist('tasks')
        for pk in pks:
            t = Task.objects.get(pk=pk)
            # TODO: There's some risk that user will end up here via browser history. Catch unique violoation exception?
            Claim.objects.create(task=t, member=nag.who, hours_claimed=t.duration.seconds/3600.0, status=Claim.CURRENT)
        return redirect('task:offers-done', auth_token=auth_token)

    else:  # GET and other methods

        # This will initally focus on open/close tasks and keyholders
        # Code depends on "Keyholder", "Open Xerocraft", and "Close Xerocraft" not changing.
        # All sets of tasks, below, include only future tasks.

        # Get the tasks that the member is already working, except for open/close tasks.
        claimed_tasks = member.tasks_claimed\
            .filter(scheduled_date__gte=datetime.today())\
            .exclude(short_desc="Open Xerocraft")\
            .exclude(short_desc="Close Xerocraft")

        if not member.is_tagged_with("Keyholder") or len(claimed_tasks) == 0:
            return redirect('task:offers-done', auth_token=auth_token)

        # Get the open/close tasks that haven't yet been claimed.
        open_tasks = Task.objects\
            .filter(short_desc="Open Xerocraft", scheduled_date__gte=datetime.today())\
            .exclude(claim__status=Claim.CURRENT)
        close_tasks = Task.objects\
            .filter(short_desc="Close Xerocraft", scheduled_date__gte=datetime.today())\
            .exclude(claim__status=Claim.CURRENT)

        # Combine all the tasks in to one list then look for open/close adjacent to other tasks.
        tasks = open_tasks | claimed_tasks | close_tasks
        tasks_to_offer = []
        for t1, t2 in zip(tasks,tasks[1:]):
            if t1.duration is None: continue
            if t1.start_time is None or t2.start_time is None: continue
            t1_start_dt = datetime.combine(t1.scheduled_date, t1.start_time)
            t2_start_dt = datetime.combine(t2.scheduled_date, t2.start_time)
            if t2_start_dt - t1_start_dt == t1.duration:
                if t1.short_desc == "Open Xerocraft" or t1.short_desc == "Close Xerocraft":
                    tasks_to_offer.append(t1)
                if t2.short_desc == "Open Xerocraft" or t2.short_desc == "Close Xerocraft":
                    tasks_to_offer.append(t2)

        if len(tasks_to_offer) > 0:
            params = {
                "member": member,
                "opens_and_closes": tasks_to_offer,
                "auth_token": auth_token,
            }
            return render(request, 'tasks/offer_adjacent_tasks.html', params)
        else:  # There aren't any future instances of interest so go to "offer adjacent tasks"
            return redirect('task:offers-done', auth_token=auth_token)
"""


def offers_done(request, auth_token):
    md5str = md5(auth_token.encode()).hexdigest()
    nag = get_object_or_404(Nag, auth_token_md5=md5str)
    member = nag.who
    try:
        settings = CalendarSettings.objects.get(who=member)
    except CalendarSettings.DoesNotExist:
        _, md5str = Member.generate_auth_token_str(
            lambda token: CalendarSettings.objects.filter(token=token).count() == 0  # uniqueness test
        )
        settings = CalendarSettings.objects.create(who=member, token=md5str)
    return render(request, 'tasks/offers_done.html', {"member": member, "settings": settings})


def task_details(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    return render(request, "tasks/task_details.html", {'task': task})


def _new_calendar(name):
    cal = Calendar()
    cal['x-wr-calname'] = name
    cal['version'] = "2.0"
    cal['calscale'] = "GREGORIAN"
    cal['method'] = "PUBLISH"
    return cal


def _add_event(cal, task):
    dtstart = datetime.combine(task.scheduled_date, task.start_time)
    event = Event()
    event.add('uid',         task.pk)
    event.add('url',         "http://xerocraft-django.herokuapp.com/tasks/task-details/%d/" % task.pk)
    event.add('summary',     task.short_desc)
    event.add('description', task.instructions.replace("\r\n", " "))
    event.add('dtstart',     dtstart)
    event.add('dtend',       dtstart + task.duration)
    event.add('dtstamp',     datetime.now())
    cal.add_component(event)


def _ical_response(cal):
    ics = cal.to_ical()
    response = HttpResponse(ics, content_type='text/calendar')
    return response


def member_calendar(request, token):  #TODO: Generalize to all users.
    member = Member.objects.get(auth_user__username='adrianb')
    cal = _new_calendar("My Xerocraft Tasks")
    for task in member.tasks_claimed.all():
        if task.scheduled_date is None or task.start_time is None or task.duration is None:
            continue
        _add_event(cal,task)
        #TODO: Add ALARM
    return _ical_response(cal)


def xerocraft_calendar(request):
    cal = _new_calendar("All Xerocraft Tasks")
    for task in Task.objects.all():
        if task.scheduled_date is None or task.start_time is None or task.duration is None:
            continue
        if task.short_desc == "Open Xerocraft" or task.short_desc == "Close Xerocraft":
            continue
        _add_event(cal,task)
        # Intentionally lacks ALARM
    return _ical_response(cal)


def resource_calendar(request):
    cal = _new_calendar("Xerocraft Resource Usage")
    #for task in Task.objects.all():
    #    if task.scheduled_date is None or task.start_time is None or task.duration is None:
    #        continue
    #    _add_event(cal,task)
    #    # Intentionally lacks ALARM
    return _ical_response(cal)

