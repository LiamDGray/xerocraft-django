module TimeSheetCommon exposing (infoDiv)


import Html exposing (Html, text, div, span)
import Html.Attributes exposing (style)

import Types exposing (..)
import CalendarDate
import Duration
import XisRestApi exposing (Task, Claim, Work, WorkNoteData)
import Wizard.SceneUtils exposing (vspace, px, pt, textAreaColor, (=>))
import PointInTime exposing (PointInTime)


-----------------------------------------------------------------------------
-- UTILITIES
-----------------------------------------------------------------------------

infoDiv : PointInTime -> Task -> Claim -> Work -> Maybe String -> Html Msg
infoDiv curr task claim work otherWorkDesc =
  let
    today = PointInTime.toCalendarDate curr
    dateStr = CalendarDate.format "%a, %b %ddd" work.data.workDate
    dateColor = if CalendarDate.equal today work.data.workDate then "black" else "red"
    workDurStr =  case work.data.workDuration of
      Nothing -> ""
      Just dur -> Duration.toString dur ++ " on "
  in
    div [infoToVerifyStyle]
      [ text ("\"" ++ task.data.shortDesc ++ "\"")
      , vspace 20
      , text workDurStr
      , span [style ["color"=>dateColor]] [text dateStr]
        , case otherWorkDesc of
            Just owd ->
              div [otherWorkDescStyle] [vspace 20, text owd]
            Nothing ->
              text ""

      ]

-----------------------------------------------------------------------------
-- STYLES
-----------------------------------------------------------------------------


infoToVerifyStyle = style
  [ "display" => "inline-block"
  , "padding" => px 20
  , "background" => textAreaColor
  , "border-width" => px 1
  , "border-color" => "black"
  --"border-style" => "solid"
  , "border-radius" => px 10
  , "width" => px 500
  ]

otherWorkDescStyle = style
  [ "line-height" => "1"
  , "font-size" => pt 20
  ]
