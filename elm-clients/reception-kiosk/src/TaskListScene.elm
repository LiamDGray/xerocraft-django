
module TaskListScene exposing
  ( init
  , sceneWillAppear
  , update
  , view
  , TaskListModel
  )

-- Standard
import Html exposing (Html, text, div)
import Html.Attributes exposing (style)
import Http
import Date
import Time exposing (Time)

-- Third Party
import Material.Toggles as Toggles
import Material.Options as Options exposing (css)
import Material.List as Lists
import Maybe.Extra as MaybeX exposing (isNothing)
import List.Extra as ListX

-- Local
import XisRestApi as XisApi exposing (..)
import Wizard.SceneUtils exposing (..)
import Types exposing (..)
import CheckInScene exposing (CheckInModel)
import Fetchable exposing (..)
import DjangoRestFramework exposing (getIdFromUrl)


-----------------------------------------------------------------------------
-- CONSTANTS
-----------------------------------------------------------------------------

staffingStatus_STAFFED = "S"  -- As defined in Django backend.
taskPriority_HIGH = "H"  -- As defined in Django backend.

-----------------------------------------------------------------------------
-- INIT
-----------------------------------------------------------------------------

type alias TaskListModel =
  { todaysTasks : Fetchable (List XisApi.Task)
  , workableTasks : List XisApi.Task
  , selectedTask : Maybe XisApi.Task
  , badNews : List String
  }

-- This type alias describes the type of kiosk model that this scene requires.
type alias KioskModel a =
  (SceneUtilModel
    { a
    | currTime : Time
    , taskListModel : TaskListModel
    , checkInModel : CheckInModel
    , xisSession : XisApi.Session Msg
    }
  )

init : Flags -> (TaskListModel, Cmd Msg)
init flags =
  let sceneModel =
    { todaysTasks = Pending
    , workableTasks = []
    , selectedTask = Nothing
    , badNews = []
    }
  in (sceneModel, Cmd.none)


-----------------------------------------------------------------------------
-- SCENE WILL APPEAR
-----------------------------------------------------------------------------

sceneWillAppear : KioskModel a -> Scene -> (TaskListModel, Cmd Msg)
sceneWillAppear kioskModel appearingScene =
  case appearingScene of

    ReasonForVisit ->
      -- Start fetching workable tasks b/c they *might* be on their way to this (TaskList) scene.
      let
        currDate = Date.fromTime kioskModel.currTime
        cmd = kioskModel.xisSession.getTaskList
          (Just [ScheduledDateEquals currDate])
          (TaskListVector << TaskListResult)
      in
        (kioskModel.taskListModel, cmd)

    _ ->
      (kioskModel.taskListModel, Cmd.none)


-----------------------------------------------------------------------------
-- UPDATE
-----------------------------------------------------------------------------

update : TaskListMsg -> KioskModel a -> (TaskListModel, Cmd Msg)
update msg kioskModel =
  let
    sceneModel = kioskModel.taskListModel
    flags = kioskModel.flags
    memberNum = kioskModel.checkInModel.memberNum

  in case msg of

    TaskListResult (Ok {results, next}) ->
      -- TODO: Deal with the possibility of paged results (i.e. next is not Nothing)?
      let
        -- "Other Work" is offered to everybody, whether or not they are explicitly eligible to work it:
        otherWorkTaskTest task = task.shortDesc == "Other Work"
        otherWorkTask = List.filter otherWorkTaskTest results
        -- The more normal case is to offer up tasks that the user can claim:
        memberCanClaim = kioskModel.xisSession.memberCanClaimTask memberNum
        claimableTasks = List.filter memberCanClaim results
        -- The offered/workable tasks are the union of claimable tasks and the "Other Work" task.
        workableTasks = claimableTasks ++ otherWorkTask

        -- We also want to run through the claims associated with today's tasks, so kick that off here:
        claimListFilters task =
          Just
            [ ClaimedTaskEquals task.id
            , ClaimingMemberEquals memberNum
            , ClaimStatusEquals CurrentClaimStatus
            ]
        taskToClaimListCmd task = kioskModel.xisSession.getClaimList (claimListFilters task) (TaskListVector << ClaimListResult)
        cmdList = List.map taskToClaimListCmd results

      in
        ({sceneModel | todaysTasks=Received results, workableTasks=workableTasks}, Cmd.batch cmdList)

    ClaimListResult (Ok {results, next}) ->
      -- TODO: Deal with the possibility of paged results (i.e. next is not Nothing)?
      -- ASSERT: There will be 0 or 1 result because of the particular query and database uniqueness constraints.
      case List.head results of
         Just claim ->
           let
             taskNum = Result.withDefault -1 (getIdFromUrl claim.claimedTask)
             hasTaskNum taskNum task = task.id == taskNum
             todaysTaskList = Fetchable.withDefault [] sceneModel.todaysTasks
             task = ListX.find (hasTaskNum taskNum) todaysTaskList
           in
             case task of
               Nothing -> (sceneModel, Cmd.none)
               Just t -> ({sceneModel | selectedTask=Just t, workableTasks=t::sceneModel.workableTasks}, Cmd.none)
         Nothing ->
           (sceneModel, Cmd.none)

    ToggleTask toggledTask ->
      ({sceneModel | selectedTask=Just toggledTask, badNews=[]}, Cmd.none)

    ValidateTaskChoice ->
      case sceneModel.selectedTask of
        Just task ->
          (sceneModel, segueTo VolunteerInDone)
        Nothing ->
          ({sceneModel | badNews=["You must choose a task to work!"]}, Cmd.none)

    -- -- -- -- ERROR HANDLERS -- -- -- --

    TaskListResult (Err error) ->
      ({sceneModel | todaysTasks=Failed (toString error)}, Cmd.none)

    ClaimListResult (Err error) ->
      ({sceneModel | badNews=[toString error]}, Cmd.none)


-----------------------------------------------------------------------------
-- VIEW
-----------------------------------------------------------------------------

idxTaskListScene = mdlIdBase TaskList


view : KioskModel a -> Html Msg
view kioskModel =
  let sceneModel = kioskModel.taskListModel
  in case sceneModel.todaysTasks of

    Pending -> waitingView kioskModel
    Received tasks -> chooseView kioskModel sceneModel.workableTasks
    Failed err -> errorView kioskModel err


waitingView : KioskModel a -> Html Msg
waitingView kioskModel =
  let
    sceneModel = kioskModel.taskListModel
  in
    genericScene kioskModel
      "One Moment Please!"
      "I'm fetching a list of tasks for you"
      (text "")  -- REVIEW: Probably won't be on-screen long enough to merit a spinny graphic.
      [] -- no buttons
      [] -- no errors


errorView : KioskModel a -> String -> Html Msg
errorView kioskModel err =
  let
    sceneModel = kioskModel.taskListModel
  in
    genericScene kioskModel
      "Choose a Task"
      "Please see a staff member"
      (text "")
      [ ButtonSpec "OK" (WizardVector <| Push <| CheckInDone) ]
      [err]


chooseView : KioskModel a -> List XisApi.Task -> Html Msg
chooseView kioskModel tasks =
  let
    sceneModel = kioskModel.taskListModel
  in
    genericScene kioskModel
      "Choose a Task"
      "Here are some you can work"
      ( taskChoices kioskModel tasks)
      [ ButtonSpec "OK" (TaskListVector <| ValidateTaskChoice) ]
      sceneModel.badNews


taskChoices : KioskModel a -> List XisApi.Task -> Html Msg
taskChoices kioskModel tasks =
  let
    sceneModel = kioskModel.taskListModel
  in
    div [taskListStyle]
      ([vspace 30] ++ List.indexedMap
        (\index wt ->
          div [taskDivStyle (if wt.priority == HighPriority then "#ccffcc" else "#dddddd")]
            [ Toggles.radio MdlVector [idxTaskListScene, index] kioskModel.mdl
              [ Toggles.value
                (case sceneModel.selectedTask of
                  Nothing -> False
                  Just st -> st == wt
                )
              , Options.onToggle (TaskListVector <| ToggleTask <| wt)
              ]
              [text wt.shortDesc]
            ]
        )
        tasks
      )


-----------------------------------------------------------------------------
-- STYLES
-----------------------------------------------------------------------------

taskListStyle = style
  [ "width" => "500px"
  , "margin-left" => "auto"
  , "margin-right" => "auto"
  , "text-align" => "left"
  ]

taskDivStyle color = style
  [ "background-color" => color
  , "padding" => "10px"
  , "margin" => "15px"
  , "border-radius" => "20px"
  ]
