var routes = {};

function decodeHash(fullHash) {
  var hash = fullHash.substring(1);
  var hashParts = hash.split("?");
  var view = hashParts[0];
  var params = {};
  if (hashParts.length > 1) {
    var paramsList = hashParts[1].split("&");
    for (var i=0; i<paramsList.length; i++) {
      var t = paramsList[i].split("=");
      params[t[0]] = decodeURIComponent(t[1]);
    }
  }
  return { "view":view, "params":params }; 
}

function genHash(state) {
  var hash = "#" + state["view"];
  var i = 0;
  for (var item in state["params"]) {
    if (i == 0) hash += "?";
    else hash += "&";
    hash += item + "=" + encodeURIComponent(state["params"][item]);
    i++;
  }
  return hash;
}

async function changeView(data) {
  if (routes.hasOwnProperty(data.view)) {
    var result = await routes[data.view](data.params);
  } else {
    var result = await routes.default(data.params);
  }
  ReactDOM.render(result, document.getElementById("reactroot"));
}

function setView(view, params) {
  window.location.hash = genHash({"view":view, "params":params});
}

function triggerRoute() {
  changeView(decodeHash(window.location.hash));
}

window.addEventListener("hashchange", triggerRoute, false);

