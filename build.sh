#!/bin/bash
# Pack application using new JavaScript features for old clients.

if [[ ! -e ".babelrc" ]]
then
    echo '{
  "presets": ["es2015", "react"],
  "plugins": ["syntax-async-functions","transform-regenerator",
              "transform-class-properties", "babel-plugin-transform-object-rest-spread"]
}' > .babelrc
fi
if [[ ! -e "node_modules" ]]
then
    npm install
fi

echo "'use strict';" > bundle-min.js
cat node_modules/babel-polyfill/browser.js >> bundle-min.js
cat node_modules/react/umd/react.production.min.js >> bundle-min.js
cat node_modules/react-dom/umd/react-dom.production.min.js >> bundle-min.js
rm lib/*.js
./node_modules/.bin/babel src --out-dir lib
cat lib/*.js > bundle.js
./node_modules/.bin/babel main.js --out-dir lib
cat lib/main.js >> bundle.js
./node_modules/.bin/uglifyjs --compress --comments '/[Ll]icense|copyright|http/' -- bundle.js >> bundle-min.js
mv bundle-min.js bundle.js
grep -vF '!Dev!' main.html | sed 's/<!-- !Compiled! \(.*\) -->/\1/g' > index.html

