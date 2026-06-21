// Runtime configuration for the static frontend.
//
// The API base URL is auto-detected so the production bundle works for any
// visitor with no build step:
//   - served from localhost / 127.0.0.1  -> local dev API (http://localhost:8000)
//   - served from any other host          -> public API (https://water-api.example.com)
//
// To force a specific API (e.g. a staging backend), replace this block with a
// single assignment, for example:
//   window.APP_CONFIG = { apiBase: "https://water-api.example.com" };
(function () {
  var host = window.location.hostname;
  var isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  window.APP_CONFIG = {
    apiBase: isLocal ? "http://localhost:8000" : "https://water-api.example.com"
  };
})();
