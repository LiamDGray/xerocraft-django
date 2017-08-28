#!/usr/bin/env bash
# transpile.sh executes with working directory $ProjectFileDir$

set -x

cd members/elm-clients/

IN=ReceptionKiosk.elm
OUT=../static/members/ReceptionKiosk.js

if node_modules/.bin/elm-make --yes $IN --output=$OUT
then
    sed -i "1i// Generated by Elm" $OUT
fi
