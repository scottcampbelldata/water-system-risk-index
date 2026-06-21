// Runtime configuration for the static frontend.
//
// Local development talks to the FastAPI backend on localhost. For the
// Cloudflare Pages production build, set this to the public API origin
// (e.g. via a Pages build step that rewrites this file, or by editing it
// before deploy):
//
//   window.APP_CONFIG = { apiBase: "https://water-api.scottcampbell.io" };
//
window.APP_CONFIG = {
  apiBase: "https://water-api.scottcampbell.io"
};
