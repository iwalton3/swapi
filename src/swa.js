function jsonRequest(url, data) {
  return new Promise(function (resolve, reject) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.onreadystatechange = function(e) {
      if (xhr.readyState === 4 && xhr.status !== 200) {
        reject(xhr.status);
      }
    }
    xhr.ontimeout = function () {
      reject('timeout');
    }
    xhr.onloadend = function (result) {
      var res = JSON.parse(result.target.response);
      if (!res.success) {
        console.log(res.error + ": " + res.error_message);
        reject(res.error);
      } else {
        resolve(res.result);
      }
    };
    xhr.send(JSON.stringify(data));
  })
}

class SimpleWebAPI {
  constructor(url) {
    this.url = url;
  }
  async callMethod(method, args) {
    return await jsonRequest(this.url, {"method":method,"args":args,"version":2});
  }
  async genMethods() {
    var methods = await this.callMethod("getMethods",[]);
    var api = this;
    methods.forEach(function(method) {
      api[method] = async function() {
        return await this.callMethod(method, Array.from(arguments));
      };
    });
  }
}

