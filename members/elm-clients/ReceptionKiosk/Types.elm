module ReceptionKiosk.Types exposing (..)

-- Standard
import Http

-- Third Party
import Material
import List.Nonempty exposing (Nonempty)

-- Local
import ReceptionKiosk.Backend exposing (..)
import TaskApi exposing (..)

-----------------------------------------------------------------------------
-- FLAGS
-----------------------------------------------------------------------------

type alias Flags =
  { csrfToken: String
  , orgName: String
  , bannerTopUrl: String
  , bannerBottomUrl: String
  , discoveryMethodsUrl: String
  , checkedInAcctsUrl: String
  , matchingAcctsUrl: String
  , logVisitEventUrl: String
  , scrapeLoginsUrl: String
  }

-----------------------------------------------------------------------------
-- SCENES
-----------------------------------------------------------------------------

type Scene
  = CheckIn
  | CheckInDone
  | CheckOut
  | CheckOutDone
  | EmailInUse
  | HowDidYouHear
  | SignUpDone
  | NewMember
  | NewUser
  | ReasonForVisit
  | VolunteerIn
  | Waiver
  | Welcome

-----------------------------------------------------------------------------
-- MSG TYPES
-----------------------------------------------------------------------------

type CheckInMsg
  = UpdateMatchingAccts (Result Http.Error MatchingAcctInfo)
  | UpdateFlexId String
  | UpdateMemberNum Int

type CheckOutMsg
  = UpdateCheckedInAccts (Result Http.Error MatchingAcctInfo)
  | LogCheckOut Int
  | CheckOutSceneWillAppear

type HowDidYouHearMsg
  = AccDiscoveryMethods (Result Http.Error DiscoveryMethodInfo)  -- "Acc" means "accumulate"
  | ToggleDiscoveryMethod DiscoveryMethod

type NewMemberMsg
  = UpdateFirstName String
  | UpdateLastName String
  | UpdateEmail String
  | ToggleIsAdult
  | Validate
  | ValidateEmailUnique (Result Http.Error MatchingAcctInfo)

type NewUserMsg
  = ValidateUserNameAndPw
  | ValidateUserNameUnique (Result Http.Error MatchingAcctInfo)
  | UpdateUserName String
  | UpdatePassword1 String
  | UpdatePassword2 String

type ReasonForVisitMsg
  = UpdateReasonForVisit ReasonForVisit
  | ValidateReason
  | LogCheckInResult (Result Http.Error GenericResult)

type VolunteerInMsg
  = CalendarPageResult (Result Http.Error CalendarPage)
  | ToggleTask OpsTask
  | VolunteerInSceneWillAppear

type WaiverMsg
  = ShowSignaturePad String
  | ClearSignaturePad String
  | GetSignature
  | UpdateSignature String  -- String is a data URL representation of an image.
  | AccountCreationResult (Result Http.Error String)
  | WaiverSceneWillAppear

type WelcomeMsg
  = WelcomeSceneWillAppear

type Msg
  = MdlVector (Material.Msg Msg)
  | WizardVector WizardMsg
  | CheckInVector CheckInMsg
  | CheckOutVector CheckOutMsg
  | HowDidYouHearVector HowDidYouHearMsg
  | NewMemberVector NewMemberMsg
  | NewUserVector NewUserMsg
  | ReasonForVisitVector ReasonForVisitMsg
  | VolunteerInVector VolunteerInMsg
  | WaiverVector WaiverMsg
  | WelcomeVector WelcomeMsg

type WizardMsg
  = Push Scene
  | RebaseTo Scene
  | Pop
  | Reset
  | SceneWillAppear Scene
