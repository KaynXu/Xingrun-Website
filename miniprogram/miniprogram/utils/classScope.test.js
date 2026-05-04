const assert = require('node:assert/strict');
const test = require('node:test');

const {
  isPrimarySchoolBinding,
  isPrimarySchoolClass,
} = require('./classScope');

test('isPrimarySchoolClass accepts only primary-school class labels', () => {
  assert.equal(isPrimarySchoolClass('六年级 1 班'), true);
  assert.equal(isPrimarySchoolClass('小学三年级数学班'), true);
  assert.equal(isPrimarySchoolClass('小五培优班'), true);
  assert.equal(isPrimarySchoolClass('初一 1 班'), false);
  assert.equal(isPrimarySchoolClass('七年级 2 班'), false);
  assert.equal(isPrimarySchoolClass('高一年级 1 班'), false);
});

test('isPrimarySchoolBinding prefers explicit class grade when present', () => {
  assert.equal(isPrimarySchoolBinding({ className: '数学强化班', classGrade: '六年级' }), true);
  assert.equal(isPrimarySchoolBinding({ className: '数学强化班', class_grade: '初一' }), false);
  assert.equal(isPrimarySchoolBinding({ className: '初一 1 班', classGrade: '六年级' }), false);
});
