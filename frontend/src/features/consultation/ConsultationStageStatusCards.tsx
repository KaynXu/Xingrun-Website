import { CheckCircle2 } from 'lucide-react';

import type { ClassItem } from '../../appTypes';
import { getCurrentClassDisplayNameById } from '../../classDisplay';
import { cn } from '../../workspaceShared';
import type { ConsultationFormValues, ConsultationTeacherOption } from './consultationTypes';

export type ConsultationStageStatusSection = 'base' | 'communication' | 'trial' | 'result';

type StatusItem = {
  label: string;
  value: string;
  done: boolean;
  teacherField?: 'teacher_id' | 'communication_teacher_added' | 'test_teacher' | 'trial_teacher' | 'teaching_teacher';
  classField?: 'success_class_id';
};

const hasText = (value: string | null | undefined): boolean => Boolean(value?.trim());

function buildStatusItems(values: ConsultationFormValues, classes: ClassItem[], section: ConsultationStageStatusSection): StatusItem[] {
  const completed = new Set(Array.isArray(values.completed_stages) ? values.completed_stages : []);
  const customerWechatDone = completed.has('已加小客服微信') || values.flow_stage === '已加小客服微信' || values.customer_service_added === '已添加';
  const teacherWechatDone = completed.has('已加对应教师微信') || values.flow_stage === '已加对应教师微信' || hasText(values.communication_teacher_added) || hasText(values.receiving_teacher);
  const testDone = completed.has('待测试') || values.flow_stage === '待测试' || values.test_taken === '是' || hasText(values.test_teacher);
  const successClassName = getCurrentClassDisplayNameById(classes, values.success_class_id) || values.success_class_manual;

  if (section === 'base') {
    return [
      { label: '客服老师', value: values.customer_service_teacher || (customerWechatDone ? '雷老师' : '未选择'), done: customerWechatDone, teacherField: undefined },
      { label: '负责教师VX', value: values.receiving_teacher || '未选择', done: hasText(values.receiving_teacher), teacherField: 'teacher_id' },
    ];
  }
  if (section === 'communication') {
    return [
      { label: '沟通教师', value: values.communication_teacher_added || values.receiving_teacher || '未选择', done: teacherWechatDone, teacherField: 'communication_teacher_added' },
      { label: '测试教师', value: values.test_teacher || '未选择', done: testDone && hasText(values.test_teacher), teacherField: 'test_teacher' },
    ];
  }
  if (section === 'trial') {
    return [
      { label: '试听教师', value: values.trial_teacher || '未选择', done: hasText(values.trial_teacher), teacherField: 'trial_teacher' },
    ];
  }
  return [
    { label: '带课教师', value: values.teaching_teacher || '未选择', done: hasText(values.teaching_teacher), teacherField: 'teaching_teacher' },
    { label: '进班班级', value: successClassName || '未选择', done: Boolean(values.success_class_id || hasText(values.success_class_manual)), classField: 'success_class_id' },
  ];
}

export function ConsultationStageStatusCards({
  values,
  classes,
  section,
  className = '',
  teacherOptions = [],
  onTeacherChange,
  onClassChange,
}: {
  values: ConsultationFormValues;
  classes: ClassItem[];
  section: ConsultationStageStatusSection;
  className?: string;
  teacherOptions?: ConsultationTeacherOption[];
  onTeacherChange?: (field: NonNullable<StatusItem['teacherField']>, value: string) => void;
  onClassChange?: (classId: number | null) => void;
}) {
  const items = buildStatusItems(values, classes, section);

  return (
    <div className={cn('my-3 grid gap-2 sm:grid-cols-2', className)}>
      {items.map((item) => {
        const selectable = Boolean((item.teacherField && onTeacherChange) || (item.classField && onClassChange));
        return (
          <label
            key={`${section}-${item.label}`}
            className={cn(
              'relative flex min-h-10 min-w-0 items-center justify-between gap-2 rounded-xl border px-3 py-2 text-sm font-bold',
              item.done
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-500/10 dark:text-emerald-200'
                : 'border-[#D9EEF7] bg-white text-[#55708D] dark:border-white/10 dark:bg-white/5 dark:text-slate-300',
              selectable && 'cursor-pointer hover:border-sky-300 hover:bg-sky-50/70 dark:hover:bg-white/10',
            )}
          >
            <span className="pointer-events-none min-w-0 truncate">{item.label}：{item.value}</span>
            {item.done ? <CheckCircle2 size={16} className="pointer-events-none shrink-0" /> : null}
            {selectable && item.teacherField ? (
              <select
                value={item.value === '未选择' ? '' : item.value}
                onChange={(event) => onTeacherChange?.(item.teacherField!, event.target.value)}
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                aria-label={`选择${item.label}`}
              >
                <option value="">请选择老师</option>
                {teacherOptions.map((option) => (
                  <option key={`${item.teacherField}-${option.teacher_id}`} value={item.teacherField === 'teacher_id' ? option.teacher_id : option.display_name}>
                    {option.display_name}
                  </option>
                ))}
              </select>
            ) : null}
            {selectable && item.classField ? (
              <select
                value={values.success_class_id ?? ''}
                onChange={(event) => onClassChange?.(event.target.value ? Number(event.target.value) : null)}
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                aria-label={`选择${item.label}`}
              >
                <option value="">请选择班级</option>
                {classes.map((classItem) => (
                  <option key={`${item.classField}-${classItem.id}`} value={classItem.id}>
                    {getCurrentClassDisplayNameById(classes, classItem.id)}
                  </option>
                ))}
              </select>
            ) : null}
          </label>
        );
      })}
    </div>
  );
}
