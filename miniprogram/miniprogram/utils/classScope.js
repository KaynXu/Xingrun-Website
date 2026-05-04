const PRIMARY_GRADE_PATTERN = /(?:小学|小[一二三四五六123456]|[一二三四五六123456]年级)/;
const SECONDARY_GRADE_PATTERN = /(?:初中|高中|初[一二三123]|高[一二三123]|[七八九789]年级|十[一二]?年级|1[0-2]年级)/;

function getBindingClassName(binding) {
  const source = binding && typeof binding === 'object' ? binding : {};
  return String(source.className || source.class_name || '').trim();
}

function getBindingClassGrade(binding) {
  const source = binding && typeof binding === 'object' ? binding : {};
  return String(source.classGrade || source.class_grade || source.grade || '').trim();
}

function isPrimarySchoolClass(className, classGrade) {
  const text = `${String(className || '').trim()} ${String(classGrade || '').trim()}`;
  if (SECONDARY_GRADE_PATTERN.test(text)) {
    return false;
  }
  return PRIMARY_GRADE_PATTERN.test(text);
}

function isPrimarySchoolBinding(binding) {
  return isPrimarySchoolClass(getBindingClassName(binding), getBindingClassGrade(binding));
}

module.exports = {
  getBindingClassGrade,
  getBindingClassName,
  isPrimarySchoolBinding,
  isPrimarySchoolClass,
};
