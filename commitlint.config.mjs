// Self-contained Conventional Commits config (no `extends`, no node_modules).
export default {
  rules: {
    'type-empty': [2, 'never'],
    'type-case': [2, 'always', 'lower-case'],
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'perf', 'refactor', 'docs', 'test', 'ci', 'chore', 'build', 'style', 'revert'],
    ],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'header-max-length': [2, 'always', 100],
    'body-leading-blank': [2, 'always'],
    'footer-leading-blank': [2, 'always'],
  },
};
