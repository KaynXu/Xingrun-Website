export const consultationProcessStages = [
  '已加小客服微信',
  '已加对应教师微信',
  '正在沟通细节',
  '待测试',
  '待试听',
] as const;

export const consultationOverStage = 'Over' as const;

export type ConsultationProcessStage = typeof consultationProcessStages[number];
export type ConsultationOverStage = typeof consultationOverStage;
export type ConsultationFlowStage = ConsultationProcessStage | ConsultationOverStage;
export type ConsultationClosingResult = '' | 'success' | 'failed';
export type ConsultationFlowLightColor = 'white' | 'green' | 'blue' | 'red';
export type ConsultationStageContent = Record<string, string | number | boolean | null | undefined>;

export interface ConsultationFlowLight {
  stage: ConsultationFlowStage;
  color: ConsultationFlowLightColor;
}

export interface ConsultationFlowState {
  flowStage: ConsultationFlowStage;
  completedStages: ConsultationProcessStage[];
  stageContent: Partial<Record<ConsultationProcessStage, ConsultationStageContent>>;
  closingResult: ConsultationClosingResult;
  overContent?: ConsultationStageContent;
  previousFlowStage?: ConsultationProcessStage;
  linkedClassId?: number;
  linkedStudentProfileId?: number;
}

export interface ConsultationFlowStateInput {
  flowStage?: string;
  completedStages?: string[];
  stageContent?: Partial<Record<string, ConsultationStageContent>>;
  closingResult?: string;
  overContent?: ConsultationStageContent;
  previousFlowStage?: string;
  linkedClassId?: number;
  linkedStudentProfileId?: number;
}

function isConsultationProcessStage(stage: string): stage is ConsultationProcessStage {
  return consultationProcessStages.includes(stage as ConsultationProcessStage);
}

function normalizeClosingResult(value: string | undefined): ConsultationClosingResult {
  return value === 'success' || value === 'failed' ? value : '';
}

function uniqueProcessStages(stages: string[] | undefined): ConsultationProcessStage[] {
  const seen = new Set<ConsultationProcessStage>();
  return (stages || []).filter((stage): stage is ConsultationProcessStage => {
    if (!isConsultationProcessStage(stage) || seen.has(stage)) return false;
    seen.add(stage);
    return true;
  });
}

function sortByFlowOrder(stages: ConsultationProcessStage[]): ConsultationProcessStage[] {
  return [...stages].sort((a, b) => consultationProcessStages.indexOf(a) - consultationProcessStages.indexOf(b));
}

function getLastCompletedStage(stages: ConsultationProcessStage[]): ConsultationProcessStage {
  return sortByFlowOrder(stages).at(-1) || consultationProcessStages[0];
}

function normalizeStageContent(
  content: Partial<Record<string, ConsultationStageContent>> | undefined,
): Partial<Record<ConsultationProcessStage, ConsultationStageContent>> {
  return Object.fromEntries(
    Object.entries(content || {}).filter(([stage]) => isConsultationProcessStage(stage)),
  ) as Partial<Record<ConsultationProcessStage, ConsultationStageContent>>;
}

function withoutStageContent(
  content: Partial<Record<ConsultationProcessStage, ConsultationStageContent>>,
  stage: ConsultationProcessStage,
): Partial<Record<ConsultationProcessStage, ConsultationStageContent>> {
  const next = { ...content };
  delete next[stage];
  return next;
}

export function createConsultationFlowState(input: ConsultationFlowStateInput = {}): ConsultationFlowState {
  const completedStages = uniqueProcessStages(input.completedStages);
  const closingResult = normalizeClosingResult(input.closingResult);
  const requestedStage = input.flowStage || getLastCompletedStage(completedStages);
  const flowStage: ConsultationFlowStage = requestedStage === consultationOverStage
    ? consultationOverStage
    : isConsultationProcessStage(requestedStage)
      ? requestedStage
      : getLastCompletedStage(completedStages);

  return {
    flowStage,
    completedStages,
    stageContent: normalizeStageContent(input.stageContent),
    closingResult,
    overContent: input.overContent,
    previousFlowStage: isConsultationProcessStage(input.previousFlowStage || '') ? input.previousFlowStage as ConsultationProcessStage : undefined,
    linkedClassId: input.linkedClassId,
    linkedStudentProfileId: input.linkedStudentProfileId,
  };
}

export function calculateConsultationFlowLights(state: ConsultationFlowState): ConsultationFlowLight[] {
  const completedSet = new Set(state.completedStages);
  const currentIndex = isConsultationProcessStage(state.flowStage)
    ? consultationProcessStages.indexOf(state.flowStage)
    : Number.POSITIVE_INFINITY;
  const processLights = consultationProcessStages.map((stage, index): ConsultationFlowLight => {
    if (state.flowStage === stage && completedSet.has(stage)) {
      return { stage, color: 'blue' };
    }
    if (completedSet.has(stage) && index < currentIndex) {
      return { stage, color: 'green' };
    }
    return { stage, color: 'white' };
  });

  const overColor: ConsultationFlowLightColor = state.flowStage === consultationOverStage
    ? state.closingResult === 'failed'
      ? 'red'
      : 'blue'
    : 'white';

  return [...processLights, { stage: consultationOverStage, color: overColor }];
}

export function completeConsultationStage(
  state: ConsultationFlowState,
  stage: ConsultationProcessStage,
  content: ConsultationStageContent = {},
): ConsultationFlowState {
  const completedStages = sortByFlowOrder(uniqueProcessStages([...state.completedStages, stage]));
  return {
    ...state,
    flowStage: getLastCompletedStage(completedStages),
    completedStages,
    stageContent: {
      ...state.stageContent,
      [stage]: content,
    },
    closingResult: '',
    overContent: undefined,
    previousFlowStage: undefined,
  };
}

export function cancelConsultationStage(
  state: ConsultationFlowState,
  stage: ConsultationProcessStage,
): ConsultationFlowState {
  const completedStages = state.completedStages.filter((item) => item !== stage);
  return {
    ...state,
    flowStage: getLastCompletedStage(completedStages),
    completedStages,
    stageContent: withoutStageContent(state.stageContent, stage),
    closingResult: '',
    overContent: undefined,
    previousFlowStage: undefined,
  };
}

export function setConsultationCurrentStage(
  state: ConsultationFlowState,
  stage: ConsultationProcessStage,
  content: ConsultationStageContent = {},
): ConsultationFlowState {
  const targetIndex = consultationProcessStages.indexOf(stage);
  const completedStages = sortByFlowOrder(uniqueProcessStages([...state.completedStages, stage]))
    .filter((item) => consultationProcessStages.indexOf(item) <= targetIndex);
  const stageContent = Object.fromEntries(
    Object.entries({
      ...state.stageContent,
      [stage]: content,
    }).filter(([key]) => isConsultationProcessStage(key) && consultationProcessStages.indexOf(key) <= targetIndex),
  ) as Partial<Record<ConsultationProcessStage, ConsultationStageContent>>;

  return {
    ...state,
    flowStage: stage,
    completedStages,
    stageContent,
    closingResult: '',
    overContent: undefined,
    previousFlowStage: undefined,
  };
}

export function completeConsultationOver(
  state: ConsultationFlowState,
  result: Exclude<ConsultationClosingResult, ''>,
  content: ConsultationStageContent = {},
): ConsultationFlowState {
  const completedStages = sortByFlowOrder(state.completedStages);
  return {
    ...state,
    flowStage: consultationOverStage,
    completedStages,
    closingResult: result,
    overContent: content,
    previousFlowStage: isConsultationProcessStage(state.flowStage)
      ? state.flowStage
      : getLastCompletedStage(state.completedStages),
  };
}

export function cancelConsultationOver(state: ConsultationFlowState): ConsultationFlowState {
  if (state.flowStage !== consultationOverStage) return state;
  return {
    ...state,
    flowStage: state.previousFlowStage || getLastCompletedStage(state.completedStages),
    closingResult: '',
    overContent: undefined,
    previousFlowStage: undefined,
  };
}
