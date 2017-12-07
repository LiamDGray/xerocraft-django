
module TimeSheetPt2Scene exposing
  ( init
  , sceneWillAppear
  , update
  , view
  , TimeSheetPt2Model
  )

-- Standard
import Html exposing (Html, text, div, p)
import Html.Attributes exposing (style)

-- Third Party

-- Local
import XisRestApi as XisApi exposing (..)
import Wizard.SceneUtils exposing (..)
import Types exposing (..)
import TimeSheetPt1Scene exposing (TimeSheetPt1Model)
import Fetchable exposing (..)
import PointInTime exposing (PointInTime)
import CalendarDate exposing (CalendarDate)
import ClockTime exposing (ClockTime)

-----------------------------------------------------------------------------
-- CONSTANTS
-----------------------------------------------------------------------------

idxTimeSheetPt2 = mdlIdBase TimeSheetPt2
idxOtherWorkDesc = [idxTimeSheetPt2, 1]

moreInfoReqd = "Please provide more information about the work you did."


-----------------------------------------------------------------------------
-- INIT
-----------------------------------------------------------------------------

-- This type alias describes the type of kiosk model that this scene requires.
type alias KioskModel a =
  (SceneUtilModel
    { a
    | currTime : PointInTime
    , timeSheetPt1Model : TimeSheetPt1Model
    , timeSheetPt2Model : TimeSheetPt2Model
    , xisSession : XisApi.Session Msg
    }
  )


type alias TimeSheetPt2Model =
  { records : Maybe (XisApi.Task, XisApi.Claim, XisApi.Work)
  , otherWorkDesc : String
  , badNews : List String
  }


init : Flags -> (TimeSheetPt2Model, Cmd Msg)
init flags =
  let sceneModel =
    { records = Nothing
    , otherWorkDesc = ""
    , badNews = []
    }
  in (sceneModel, Cmd.none)


-----------------------------------------------------------------------------
-- SCENE WILL APPEAR
-----------------------------------------------------------------------------

sceneWillAppear : KioskModel a -> Scene -> Scene -> (TimeSheetPt2Model, Cmd Msg)
sceneWillAppear kioskModel appearingScene vanishingScene =
  let
    sceneModel = kioskModel.timeSheetPt2Model
    prevModel = kioskModel.timeSheetPt1Model
  in
    if appearingScene == TimeSheetPt2 then

      case (prevModel.taskInProgress, prevModel.claimInProgress, prevModel.workInProgress) of

        (Received task, Received (Just claim), Received (Just work)) ->
          let
            records = Just (task, claim, work)
          in
            if task.shortDesc == "Other Work" then
              ({sceneModel | records=records}, Cmd.none)
            else
              -- User might be going forward OR BACKWARD in the wizard:
              if vanishingScene==TimeSheetPt1 then
                (sceneModel, segueTo TimeSheetPt3)
              else
                (sceneModel, pop)

        _ ->
          ({sceneModel | badNews=["Couldn't get task, claim, and work records!"]}, Cmd.none)

    else
      (sceneModel, Cmd.none)


-----------------------------------------------------------------------------
-- UPDATE
-----------------------------------------------------------------------------

update : TimeSheetPt2Msg -> KioskModel a -> (TimeSheetPt2Model, Cmd Msg)
update msg kioskModel =
  let
    sceneModel = kioskModel.timeSheetPt2Model
    xis = kioskModel.xisSession

  in case msg of

    TS2_UpdateDescription s ->
      ({sceneModel | otherWorkDesc = s}, Cmd.none)

    TS2_Continue ->
      if (sceneModel.otherWorkDesc |> String.trim |> String.length) < 10 then
        ({sceneModel | badNews=[moreInfoReqd]}, Cmd.none)
      else
        (sceneModel, segueTo TimeSheetPt3)


-----------------------------------------------------------------------------
-- VIEW
-----------------------------------------------------------------------------

view : KioskModel a -> Html Msg
view kioskModel =
  case kioskModel.timeSheetPt2Model.records of
    Just (t, c, w) -> viewNormal kioskModel t c w
    _ -> text ""


viewNormal : KioskModel a -> XisApi.Task -> XisApi.Claim -> XisApi.Work -> Html Msg
viewNormal kioskModel task claim work =
  let
    sceneModel = kioskModel.timeSheetPt2Model
    today = PointInTime.toCalendarDate kioskModel.currTime
    dateStr = CalendarDate.format "%a, %b %ddd" work.workDate
    startTime = Maybe.withDefault (ClockTime 0 0) work.workStartTime  -- Should not be Nothing
    startTimeStr = ClockTime.format "%I:%M %P" startTime
    workDur = Maybe.withDefault 0 work.workDuration  -- Should not be Nothing
  in genericScene kioskModel

  "Volunteer Timesheet"

  "Please describe the work you did"

    ( div []
      [ vspace 50
      , div [infoToVerifyStyle]
         [ text ("Task: \"" ++ task.shortDesc ++ "\"")
         , vspace 20
         , text (dateStr ++ " @ " ++ startTimeStr ++ " for " ++ (toString workDur) ++ " hrs")
         ]
      , vspace 70
      , div [textAreaContainerStyle]
          [ sceneTextArea kioskModel idxOtherWorkDesc
              "Description of work done" sceneModel.otherWorkDesc
              6 -- rows in text area
              (TimeSheetPt2Vector << TS2_UpdateDescription)
          ]

      , vspace 20
      ]
    )

    [ ButtonSpec "Continue" (TimeSheetPt2Vector <| TS2_Continue) ]

    sceneModel.badNews



-----------------------------------------------------------------------------
-- STYLES
-----------------------------------------------------------------------------

infoToVerifyStyle = style
  [ "display" => "inline-block"
  , "padding" => px 20
  , "background" => textAreaColor
  , "border-width" => px 1
  , "border-color" => "black"
  , "border-style" => "solid"
  , "border-radius" => px 10
  ]

textAreaContainerStyle = style
  [ "display" => "inline-block"
  , "padding-top" => px 20
  , "border-style" => "solid"
  , "border-width" => px 1
  , "border-radius" => px 10
  , "width" => px 550
  , "background-color" => "white"
  ]