/** @type {import('vls').VeturConfig} */
module.exports = {
  projects: [
    {
      root: '.',
      tsconfig: './tsconfig.app.json',
    },
  ],
  settings: {
    'vetur.useWorkspaceDependencies': true,
    'vetur.experimental.templateInterpolationService': true,
  },
}
