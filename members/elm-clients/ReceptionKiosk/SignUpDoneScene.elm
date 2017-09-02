
module ReceptionKiosk.SignUpDoneScene exposing (init, view, SignUpDoneModel)

-- Standard
import Html exposing (Html, text, p, br, span)

-- Third Party
import Material.Options as Options exposing (css)

-- Local
import ReceptionKiosk.Types exposing (..)
import ReceptionKiosk.SceneUtils exposing (..)
import ReceptionKiosk.NewUserScene exposing (NewUserModel)

-----------------------------------------------------------------------------
-- INIT
-----------------------------------------------------------------------------

-- TODO: There should be a time out back to Welcome

type alias SignUpDoneModel =
  {
  }

-- This type alias describes the type of kiosk model that this scene requires.
type alias KioskModel a =
  SceneUtilModel
    { a
    | signUpDoneModel : SignUpDoneModel
    , newUserModel: NewUserModel
    }

init : Flags -> (SignUpDoneModel, Cmd Msg)
init flags = ({}, Cmd.none)

-----------------------------------------------------------------------------
-- UPDATE
-----------------------------------------------------------------------------

-----------------------------------------------------------------------------
-- VIEW
-----------------------------------------------------------------------------

view : KioskModel a -> Html Msg
view kioskModel =
  let
    userModel = kioskModel.newUserModel
  in genericScene kioskModel
    "Xerocraft Account Created!"
    "Just one more thing..."
    (p [sceneTextStyle]
      [ vspace 30
      , text "You much check in each time you visit"
      , br [] []
      , text "so please remember that your userid is:"
      , vspace 40
      , span [userIdStyle] [text userModel.userName]
      , vspace 40
      , text "Click the button below to check in now!"
      ]
    )
    [ButtonSpec "Check In" (WizardVector <| Push <| CheckIn)]
