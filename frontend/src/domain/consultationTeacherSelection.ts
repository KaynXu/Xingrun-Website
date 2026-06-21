export interface ConsultationTeacherSelectionOption {
  teacher_id: string;
  display_name: string;
  aliases: string[];
}

export interface ConsultationTeacherRecommendationValues {
  completed_stages?: string[];
  flow_stage?: string;
  customer_service_teacher?: string;
  communication_teacher_added?: string;
  receiving_teacher?: string;
  teacher_id?: string;
  test_teacher?: string;
  trial_teacher?: string;
}

export interface ConsultationTeacherDraftRecommendation {
  teacherId: string;
  teacherName: string;
}

const defaultCustomerServiceTeacherPattern = /雷老师|雷文浩/i;

function normalizeTeacherSearchValue(value: string): string {
  return value.trim().toLowerCase();
}

function getTeacherOptionSearchText(option: ConsultationTeacherSelectionOption): string {
  return [option.teacher_id, option.display_name, ...option.aliases].join(' ').toLowerCase();
}

function isDefaultCustomerServiceTeacherOption(option: ConsultationTeacherSelectionOption): boolean {
  return defaultCustomerServiceTeacherPattern.test([option.teacher_id, option.display_name, ...option.aliases].join(' '));
}

function isStageSaved(values: ConsultationTeacherRecommendationValues, stage: string): boolean {
  return Boolean(values.completed_stages?.includes(stage) || values.flow_stage === stage);
}

function findTeacherOption(
  options: ConsultationTeacherSelectionOption[],
  teacherId: string,
  teacherName: string,
): ConsultationTeacherSelectionOption | undefined {
  const normalizedId = normalizeTeacherSearchValue(teacherId);
  const normalizedName = normalizeTeacherSearchValue(teacherName);
  return options.find((option) => {
    const candidates = [option.teacher_id, option.display_name, ...option.aliases].map(normalizeTeacherSearchValue);
    return Boolean(
      (normalizedId && candidates.includes(normalizedId))
      || (normalizedName && candidates.includes(normalizedName)),
    );
  });
}

export function filterConsultationTeacherOptionsForStage(
  stage: string,
  options: ConsultationTeacherSelectionOption[],
): ConsultationTeacherSelectionOption[] {
  if (stage !== '已加小客服微信') return options;
  return options.filter(isDefaultCustomerServiceTeacherOption);
}

export function searchConsultationTeacherOptions(
  options: ConsultationTeacherSelectionOption[],
  query: string,
): ConsultationTeacherSelectionOption[] {
  const normalizedQuery = normalizeTeacherSearchValue(query);
  if (!normalizedQuery) return options;
  return options.filter((option) => getTeacherOptionSearchText(option).includes(normalizedQuery));
}

export function getConsultationFlowNodeRecommendedTeacher(
  stage: string,
  values: ConsultationTeacherRecommendationValues,
  options: ConsultationTeacherSelectionOption[],
): ConsultationTeacherDraftRecommendation {
  if (stage === '已加小客服微信') {
    const defaultServiceTeacher = options.find(isDefaultCustomerServiceTeacherOption);
    return {
      teacherId: defaultServiceTeacher?.teacher_id || '',
      teacherName: defaultServiceTeacher?.display_name || '',
    };
  }

  let previousStage = '';
  let teacherId = '';
  let teacherName = '';

  if (stage === '正在沟通细节') {
    previousStage = '已加对应教师微信';
    teacherName = values.communication_teacher_added || '';
  } else if (stage === '待测试') {
    previousStage = '正在沟通细节';
    teacherId = values.teacher_id || '';
    teacherName = values.receiving_teacher || '';
  } else if (stage === '待试听') {
    previousStage = '待测试';
    teacherName = values.test_teacher || '';
  }

  if (!previousStage || !isStageSaved(values, previousStage) || (!teacherId && !teacherName)) {
    return { teacherId: '', teacherName: '' };
  }

  const matchedOption = findTeacherOption(options, teacherId, teacherName);
  return {
    teacherId: matchedOption?.teacher_id || teacherId,
    teacherName: matchedOption?.display_name || teacherName,
  };
}
