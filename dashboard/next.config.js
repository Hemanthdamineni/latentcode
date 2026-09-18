/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // CodeMend serves the dashboard against findings written by the CLI.
  // Findings are usually under <repo>/.codemend — the dashboard reads from
  // the CODEMEND_FINDINGS env var or the default .codemend in cwd.
};