
module CheckInScene exposing
  ( init
  , rfidWasSwiped
  , sceneWillAppear
  , tick
  , update
  , view
  --------------
  , CheckInModel
  )

-- Standard
import Html exposing (Html, div, text, audio)
import Html.Attributes exposing (src, autoplay)
import Http
import Time exposing (Time)
import Regex

-- Third Party
import Material
import Material.Chip as Chip
import Material.Options as Options exposing (css)
import List.Extra as ListX
import List.Nonempty exposing (Nonempty)

-- Local
import Types exposing (..)
import Wizard.SceneUtils exposing (..)
import XisRestApi as XisApi exposing (Member)
import PointInTime as PIT exposing (PointInTime)
import RfidHelper as RfidHelper exposing (RfidHelperModel, rfidCharsOnly)

-- TODO: If user is signing in after acct creation, show a username hint?


-----------------------------------------------------------------------------
-- CONSTANTS
-----------------------------------------------------------------------------


-----------------------------------------------------------------------------
-- INIT
-----------------------------------------------------------------------------

-- This type alias describes the type of kiosk model that this scene requires.
type alias KioskModel a =
  { a
  ------------------------------------
  | mdl : Material.Model
  , flags : Flags
  , sceneStack : Nonempty Scene
  ------------------------------------
  , checkInModel : CheckInModel
  , xisSession : XisApi.Session Msg
  , currTime : PointInTime
  }


-- REVIEW: flexID should be a Maybe?
type alias CheckInModel =
  { flexId : String  -- UserName or surname.
  , userNameMatches_SW : List Member  -- Matches to username
  , userNameMatches_EQ : List Member  -- Matches to username
  , lastNameMatches_SW : List Member  -- Matches to surname
  , lastNameMatches_EQ : List Member  -- Matches to surname
  , recentRfidArrivals : List Member  -- People who have recently swiped RFID.
  , checkedInMember : Maybe Member -- The member that the person checked in as.
  , badNews : List String
  }


init : Flags -> (CheckInModel, Cmd Msg)
init flags =
  let model =
    { flexId = ""  -- A harmless initial value.
    , userNameMatches_SW = []
    , userNameMatches_EQ = []
    , lastNameMatches_SW = []
    , lastNameMatches_EQ = []
    , recentRfidArrivals = []
    , checkedInMember = Nothing
    , badNews = []
    }
  in (model, Cmd.none)


-----------------------------------------------------------------------------
-- SCENE WILL APPEAR
-----------------------------------------------------------------------------

sceneWillAppear : KioskModel a -> Scene -> (CheckInModel, Cmd Msg)
sceneWillAppear kioskModel appearingScene =
  if appearingScene == CheckIn
    then
      let
        cmd1 = getRecentRfidsReadCmd kioskModel
        cmd2 = focusOnIndex idxFlexId
      in
        (kioskModel.checkInModel, Cmd.batch [cmd1, cmd2])
    else
      (kioskModel.checkInModel, Cmd.none)


-----------------------------------------------------------------------------
-- UPDATE
-----------------------------------------------------------------------------

update : CheckInMsg -> KioskModel a -> (CheckInModel, Cmd Msg)
update msg kioskModel =
  let
    sceneModel = kioskModel.checkInModel
    xis = kioskModel.xisSession

  in case msg of

    CI_UpdateFlexId rawId ->

        if Regex.contains rfidCharsOnly rawId then
          ({sceneModel | flexId=rawId}, Cmd.none)
        else if (String.length rawId) > 2 then
          let
            djId = XisApi.djangoizeId rawId
            cmd1 = xis.listMembers
              [XisApi.UsernameStartsWith djId, XisApi.IsActive True]
              (CheckInVector << (UsernamesStartingWith rawId))
            cmd2 = xis.listMembers
              [XisApi.LastNameStartsWith djId, XisApi.IsActive True]
              (CheckInVector << (LastNamesStartingWith rawId))
            cmd3 = xis.listMembers
              [XisApi.UsernameEquals djId, XisApi.IsActive True]
              (CheckInVector << (UsernamesEqualTo rawId))
            cmd4 = xis.listMembers
              [XisApi.LastNameEquals djId, XisApi.IsActive True]
              (CheckInVector << (LastNamesEqualTo rawId))
          in
            ({sceneModel | flexId=rawId}, Cmd.batch [cmd1, cmd2, cmd3, cmd4])
        else
          ({sceneModel | flexId=rawId, userNameMatches_SW=[], lastNameMatches_SW=[]}, Cmd.none)


    UsernamesStartingWith searchedId (Ok {count, results}) ->
      if searchedId == sceneModel.flexId && count < 20
      then ({sceneModel | userNameMatches_SW = results, badNews = []}, Cmd.none)
      else (sceneModel, Cmd.none)

    UsernamesEqualTo searchedId (Ok {count, results}) ->
      if searchedId == sceneModel.flexId
      then ({sceneModel | userNameMatches_EQ = results, badNews = []}, Cmd.none)
      else (sceneModel, Cmd.none)

    LastNamesStartingWith searchedId (Ok {count, results}) ->
      if searchedId == sceneModel.flexId && count < 20
      then ({sceneModel | lastNameMatches_SW = results, badNews = []}, Cmd.none)
      else (sceneModel, Cmd.none)

    LastNamesEqualTo searchedId (Ok {count, results}) ->
      if searchedId == sceneModel.flexId
      then ({sceneModel | lastNameMatches_EQ = results, badNews = []}, Cmd.none)
      else (sceneModel, Cmd.none)

    UpdateRecentRfidsRead (Ok {results}) ->
      let
        recent = List.map (.data >> .who) results
        unique = ListX.uniqueBy .id recent
      in
        ({sceneModel | recentRfidArrivals = unique}, Cmd.none)

    CI_UpdateMember (Ok member) ->
      ({sceneModel | checkedInMember=Just member, badNews=[]}, segueTo ReasonForVisit)

    ---------- ERRORS ----------

    UsernamesStartingWith searchedId (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)

    UsernamesEqualTo searchedId (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)

    LastNamesStartingWith searchedId (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)

    LastNamesEqualTo searchedId (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)

    UpdateRecentRfidsRead (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)

    CI_UpdateMember (Err error) ->
      ({sceneModel | badNews = [toString error]}, Cmd.none)


-----------------------------------------------------------------------------
-- VIEW
-----------------------------------------------------------------------------

idxCheckInScene = mdlIdBase CheckIn
idxFlexId = [idxCheckInScene, 1]


view : KioskModel a -> Html Msg
view kioskModel =
  let
    sceneModel = kioskModel.checkInModel
    clickMsg = \memb -> CheckInVector <| CI_UpdateMember <| Ok memb
    acctToChip = \memb ->
      Chip.button
        [Options.onClick (clickMsg memb)]
        [Chip.content [] [text memb.data.userName]]
    zeroIfTooLong l = if List.length l > 20 then [] else l
    matches =
      if String.isEmpty sceneModel.flexId then
        sceneModel.recentRfidArrivals
      else
        (ListX.uniqueBy .id << List.concat)
          [ zeroIfTooLong sceneModel.userNameMatches_SW
          , zeroIfTooLong sceneModel.lastNameMatches_SW
          , sceneModel.userNameMatches_EQ
          , sceneModel.lastNameMatches_EQ
          ]
  in genericScene kioskModel
    "Let's Get You Checked-In!"
    "Who are you?"
    ( div []
        (List.concat
          [ [sceneTextField kioskModel idxFlexId "Enter your Userid or Last Name" sceneModel.flexId (CheckInVector << CI_UpdateFlexId), vspace 0]
          , if List.length matches > 0
             then [vspace 50, text "Tap your userid if you see it below:", vspace 20]
             else [vspace 0]
          , List.map acctToChip matches
          , [ vspace (if List.length sceneModel.badNews > 0 then 40 else 0) ]
          , if not (List.isEmpty matches)
             then
               -- TODO: Audio tag lag can be very bad. See https://lowlag.alienbill.com/
               [audio [src "/static/members/beep-22.mp3", autoplay True] []]
             else
               [vspace 0]
          ]
        )
    )
    []  -- No buttons
    sceneModel.badNews


-----------------------------------------------------------------------------
-- TICK (called each second)
-----------------------------------------------------------------------------

tick : Time -> KioskModel a -> (CheckInModel, Cmd Msg)
tick time kioskModel =
  let
    sceneModel = kioskModel.checkInModel
    visible = sceneIsVisible kioskModel CheckIn
    inc = if visible then 1 else 0
    cmd1 =
      if visible && String.isEmpty sceneModel.flexId
        then getRecentRfidsReadCmd kioskModel
        else Cmd.none
    cmd = if visible then cmd1 else Cmd.none
  in
    (sceneModel, cmd)


-----------------------------------------------------------------------------
-- RFID WAS SWIPED
-----------------------------------------------------------------------------

rfidWasSwiped : KioskModel a -> Result String Member -> (CheckInModel, Cmd Msg)
rfidWasSwiped kioskModel result =
  let
    sceneModel = kioskModel.checkInModel
  in
    case result of
      Ok m ->
        ({sceneModel | checkedInMember=Just m, badNews=[]}, segueTo ReasonForVisit)

      Err e ->
        ({sceneModel | badNews=[toString e]}, Cmd.none)


-----------------------------------------------------------------------------
-- COMMANDS
-----------------------------------------------------------------------------

getRecentRfidsReadCmd : KioskModel a -> Cmd Msg
getRecentRfidsReadCmd kioskModel =
  let
    lowerBound = kioskModel.currTime - (15 * Time.minute)
    filters =
      [ XisApi.VEF_WhenGreaterOrEquals lowerBound
      , XisApi.VEF_EventMethodEquals XisApi.VEM_Rfid
      ]
    tagger = (CheckInVector << UpdateRecentRfidsRead)
  in
    kioskModel.xisSession.listVisitEvents filters tagger


-----------------------------------------------------------------------------
-- STYLES
-----------------------------------------------------------------------------

sceneChipCss =
  [ css "margin-left" "3px"
  , css "margin-right" "3px"
  ]
