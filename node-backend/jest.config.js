module.exports = {
    testEnvironment: 'node',
    collectCoverageFrom: [
      '**/*.js',
      '!**/node_modules/**',
      '!**/coverage/**',
      '!**/test/**'
    ],
    coverageDirectory: 'coverage/backend'
  };