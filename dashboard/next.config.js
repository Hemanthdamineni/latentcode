/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // LatentCode serves the dashboard against findings written by the CLI.
  // Findings are usually under <repo>/.latentcode — the dashboard reads from
  // the LATENTCODE_FINDINGS env var or the default .latentcode in cwd.
};