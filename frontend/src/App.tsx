/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Home,
  LayoutDashboard,
  PlusCircle,
  Library,
  Database,
  Settings,
  Search,
  Bell,
  User,
  FileText,
  Clock,
  Download,
  Trash2,
  Eye,
  EyeOff,
  Upload,
  Cpu,
  CheckCircle2,
  MoreVertical,
  Filter,
  ArrowRight,
  AlertCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// --- Types ---

type Role = 'owner' | 'member';
type Page = 'dashboard' | 'input' | 'library' | 'questions' | 'accounts' | 'settings';

interface Lesson {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  pdf_path: string;
  class_id: number | null;
  created_at: string;
}

interface Stats {
  total_lessons: number;
  month_lessons: number;
  total_pdfs: number;
  total_questions: number;
}

interface Question {
  id: number;
  lesson_id: number;
  question: string;
  answer: string;
  category: string;
  day_num: number;
}

interface QuizData {
  total: number;
  categories: Record<string, Question[]>;
}

interface ApiSettings {
  provider: string;
}

interface ClassItem {
  id: number;
  name: string;
  subject: string;
  grade: string;
}

interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  status: string;
  organization_id: number;
  organization_name: string;
  created_at: string;
}

interface RegistrationRequestItem {
  id: number;
  username: string;
  display_name: string;
  organization_name: string;
  status: string;
  created_at: string;
}

function getRoleLabel(role: Role): string {
  return role === 'owner' ? '最高权限账号' : '机构成员';
}

// --- API helper ---

function getToken(): string {
  return localStorage.getItem('xr_token') || '';
}

async function apiFetch<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const token = getToken();
  const res = await fetch(path, {
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { 'X-Auth-Token': token } : {}),
      ...(options?.headers ?? {}),
    },
    ...options,
  });
  if (res.status === 401) {
    localStorage.removeItem('xr_token');
    window.location.reload();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json() as Promise<T>;
}

// --- Components ---

const Sidebar = ({
  activePage,
  currentUser,
  setActivePage,
}: {
  activePage: Page;
  currentUser: CurrentUser;
  setActivePage: (p: Page) => void;
}) => {
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
    { id: 'input', icon: PlusCircle, label: '添加课程' },
    { id: 'library', icon: Library, label: '课程列表' },
    { id: 'questions', icon: Database, label: '题库浏览' },
    ...(currentUser.role === 'owner' ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
    { id: 'settings', icon: Settings, label: '系统设置' },
  ];

  return (
    <div className="w-64 h-screen border-r border-white/10 flex flex-col bg-black sticky top-0">
      <div className="p-6 flex items-center gap-3">
        <img src="/logo.png" alt="星润 logo" className="w-10 h-10 object-contain" />
        <h1 className="text-lg font-semibold tracking-tight">星润复习系统</h1>
      </div>

      <nav className="flex-1 px-4 py-4 space-y-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActivePage(item.id as Page)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
              activePage === item.id
                ? 'bg-blue-600/10 text-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.1)]'
                : 'text-gray-400 hover:text-gray-100 hover:bg-white/5'
            }`}
          >
            <item.icon size={20} />
            <span className="font-medium">{item.label}</span>
            {activePage === item.id && (
              <motion.div
                layoutId="active-pill"
                className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500"
              />
            )}
          </button>
        ))}
      </nav>

      <div className="p-4 mt-auto border-t border-white/10">
        <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold">
            {currentUser.display_name.slice(0, 1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{currentUser.display_name}</p>
            <p className="text-xs text-gray-500 truncate">{getRoleLabel(currentUser.role)}</p>
          </div>
          <MoreVertical size={16} className="text-gray-500" />
        </div>
      </div>
    </div>
  );
};

const Header = ({ title, onGoHome }: { title: string; onGoHome?: () => void }) => {
  return (
    <header className="h-16 border-b border-white/10 flex items-center justify-between px-8 bg-black/50 backdrop-blur-md sticky top-0 z-10">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="flex items-center gap-4">
        {onGoHome && (
          <button onClick={onGoHome} title="返回首页" className="p-2 text-gray-400 hover:text-gray-100 transition-colors">
            <Home size={20} />
          </button>
        )}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
          <input
            type="text"
            placeholder="搜索课程、题目..."
            className="bg-white/5 border border-white/10 rounded-full py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-blue-500/50 w-64 transition-all"
          />
        </div>
        <button className="p-2 text-gray-400 hover:text-gray-100 transition-colors relative">
          <Bell size={20} />
          <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border-2 border-black"></span>
        </button>
      </div>
    </header>
  );
};

const XiaojimaoLoading = ({ label = '小吉猫正在思考中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12">
    <motion.div
      animate={{
        y: [0, -10, 0],
        rotate: [0, 5, -5, 0],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      className="w-24 h-24 bg-blue-600/20 rounded-full flex items-center justify-center relative mb-4"
    >
      <div className="w-16 h-16 bg-blue-500 rounded-2xl flex items-center justify-center shadow-[0_0_30px_rgba(59,130,246,0.3)]">
        <span className="text-white text-3xl">🐱</span>
      </div>
      <motion.div
        animate={{ scale: [1, 1.2, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
        className="absolute -top-1 -right-1 w-6 h-6 bg-white rounded-full flex items-center justify-center text-[10px] text-blue-600 font-bold shadow-lg"
      >
        AI
      </motion.div>
    </motion.div>
    <p className="text-blue-400 font-medium animate-pulse">{label}</p>
    <p className="text-gray-500 text-sm mt-2">正在为您生成结构化复习资料</p>
  </div>
);

// --- Pages ---

const Dashboard = ({
  currentUser,
  setActivePage,
}: {
  currentUser: CurrentUser;
  setActivePage: (p: Page) => void;
}) => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentLessons, setRecentLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<Stats>('/api/stats'),
      apiFetch<Lesson[]>('/api/lessons'),
    ])
      .then(([s, lessons]) => {
        setStats(s);
        setRecentLessons(lessons.slice(0, 5));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const statCards = [
    { label: '本月课程', value: stats?.month_lessons ?? '—', icon: FileText, color: 'text-blue-500' },
    { label: '累计课程', value: stats?.total_lessons ?? '—', icon: Library, color: 'text-green-500' },
    { label: '已生成 PDF', value: stats?.total_pdfs ?? '—', icon: Download, color: 'text-purple-500' },
    { label: '题库题目', value: stats?.total_questions ?? '—', icon: Database, color: 'text-orange-500' },
  ];

  return (
    <div className="p-8 space-y-8">
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-blue-600/20 to-transparent border border-blue-500/20 rounded-3xl p-8 flex flex-col justify-between min-h-[200px]">
        <div>
          <h3 className="text-2xl font-bold mb-2">欢迎回来，{currentUser.display_name}</h3>
          <p className="text-gray-400 max-w-md">
            {loading
              ? '正在加载数据...'
              : `本月已记录 ${stats?.month_lessons ?? 0} 节课，累计生成 ${stats?.total_pdfs ?? 0} 份 PDF 复习资料。`}
          </p>
        </div>
        <div className="flex gap-4 mt-6">
          <button
            onClick={() => setActivePage('input')}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-semibold flex items-center gap-2 transition-all shadow-lg shadow-blue-600/20"
          >
            <PlusCircle size={20} />
            添加新课程
          </button>
          <button
            onClick={() => setActivePage('library')}
            className="bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-xl font-semibold flex items-center gap-2 transition-all"
          >
            <Library size={20} />
            查看课程列表
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {statCards.map((stat, i) => (
          <div
            key={i}
            className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-blue-500/30 transition-all group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className={`p-2 rounded-lg bg-white/5 ${stat.color}`}>
                <stat.icon size={20} />
              </div>
              <ArrowRight size={16} className="text-gray-600 group-hover:text-gray-400 transition-colors" />
            </div>
            <p className="text-sm text-gray-500">{stat.label}</p>
            <p className="text-2xl font-bold mt-1">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Recent Lessons */}
      <div className="bg-white/5 border border-white/10 rounded-3xl overflow-hidden">
        <div className="p-6 border-b border-white/10 flex items-center justify-between">
          <h4 className="font-semibold">最近课程</h4>
          <button onClick={() => setActivePage('library')} className="text-sm text-blue-500 hover:underline">
            查看全部
          </button>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : recentLessons.length === 0 ? (
          <div className="p-8 text-center text-gray-500">暂无课程记录</div>
        ) : (
          <div className="divide-y divide-white/5">
            {recentLessons.map((lesson) => (
              <div key={lesson.id} className="p-4 hover:bg-white/5 transition-colors flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center text-red-500">
                  <FileText size={24} />
                </div>
                <div className="flex-1">
                  <p className="font-medium">{lesson.topic || `${lesson.subject} 课程`}</p>
                  <p className="text-xs text-gray-500">
                    {lesson.date} • {lesson.subject} • {lesson.grade}
                  </p>
                </div>
                {lesson.pdf_path && (
                  <div className="flex gap-2">
                    <a
                      href={`/pdf/download/${lesson.id}`}
                      className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all"
                      title="下载"
                    >
                      <Download size={18} />
                    </a>
                    <a
                      href={`/pdf/${lesson.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all"
                      title="查看"
                    >
                      <Eye size={18} />
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const LessonInput = ({ onSuccess }: { onSuccess: () => void }) => {
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [lessonDate, setLessonDate] = useState(new Date().toISOString().split('T')[0]);
  const [weakPoints, setWeakPoints] = useState('');
  const [summaryText, setSummaryText] = useState('');
  const [inputType, setInputType] = useState<'text' | 'file'>('text');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiFetch<ClassItem[]>('/api/classes').then(setClasses).catch(console.error);
  }, []);

  const handleClassChange = (id: number) => {
    setClassId(id);
    const cls = classes.find((c) => c.id === id);
    if (cls?.subject) setSubject(cls.subject);
  };

  const handleAnalyze = async () => {
    if (!summaryText.trim()) return;
    setIsAnalyzing(true);
    try {
      const result = await apiFetch<{ subject: string; topic: string; weak_points: string }>('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ text: summaryText }),
      });
      if (result.subject) setSubject(result.subject);
      if (result.topic) setTopic(result.topic);
      if (result.weak_points) setWeakPoints(result.weak_points);
    } catch (e) {
      setError(e instanceof Error ? e.message : '识别失败，请重试');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    setError('');
    if (inputType === 'text' && !summaryText.trim()) {
      setError('请填写课堂笔记内容');
      return;
    }
    if (inputType === 'file' && !file) {
      setError('请选择上传文件');
      return;
    }

    setIsLoading(true);
    try {
      if (inputType === 'text') {
        await apiFetch('/api/lessons', {
          method: 'POST',
          body: JSON.stringify({
            subject,
            class_id: classId ?? 0,
            topic,
            date: lessonDate,
            weak_points: weakPoints,
            summary_text: summaryText,
          }),
        });
      } else {
        const formData = new FormData();
        formData.append('input_type', 'file');
        formData.append('subject', subject);
        formData.append('class_id', classId ? String(classId) : '0');
        formData.append('topic', topic);
        formData.append('date', lessonDate);
        formData.append('weak_points', weakPoints);
        if (file) formData.append('upload_file', file);
        const res = await fetch('/api/lessons', { method: 'POST', body: formData });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: res.statusText }));
          throw new Error((err as { error?: string }).error || res.statusText);
        }
      }
      onSuccess();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '提交失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            className="h-[60vh] flex items-center justify-center"
          >
            <XiaojimaoLoading label="小吉猫正在生成复习资料..." />
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-bold">添加新课程</h3>
                <p className="text-gray-500">上传录音或粘贴笔记，AI 将为您自动生成复习资料。</p>
              </div>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="科目"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50 w-28"
                />
                <select
                  value={classId ?? ''}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className="bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50 w-32 text-gray-300"
                >
                  <option value="" disabled className="bg-[#0a0a0a]">选择班级</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id} className="bg-[#0a0a0a]">{c.name}</option>
                  ))}
                </select>
                <input
                  type="date"
                  value={lessonDate}
                  onChange={(e) => setLessonDate(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400">
                <AlertCircle size={18} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="space-y-6">
                {/* Input type toggle */}
                <div className="flex gap-2 p-1 bg-white/5 border border-white/10 rounded-xl w-fit">
                  <button
                    onClick={() => setInputType('text')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${inputType === 'text' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                  >
                    文字笔记
                  </button>
                  <button
                    onClick={() => setInputType('file')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${inputType === 'file' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                  >
                    上传文件
                  </button>
                </div>

                {inputType === 'file' ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-white/5 border-2 border-dashed border-white/10 rounded-3xl p-12 flex flex-col items-center justify-center text-center hover:border-blue-500/50 transition-all cursor-pointer group"
                  >
                    <div className="w-16 h-16 bg-blue-600/10 rounded-2xl flex items-center justify-center text-blue-500 mb-4 group-hover:scale-110 transition-transform">
                      <Upload size={32} />
                    </div>
                    <h4 className="font-semibold mb-2">{file ? file.name : '上传课后录音或文本'}</h4>
                    <p className="text-sm text-gray-500">支持 m4a, mp3, wav, txt, md 格式</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac,.txt,.md"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                ) : null}

                <div className="p-6 bg-white/5 border border-white/10 rounded-3xl space-y-4">
                  <h4 className="font-semibold flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-blue-500" />
                    课程信息
                  </h4>
                  <input
                    type="text"
                    placeholder="课程主题（选填）"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500/50"
                  />
                  <textarea
                    placeholder="薄弱点（选填）"
                    value={weakPoints}
                    onChange={(e) => setWeakPoints(e.target.value)}
                    rows={2}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500/50 resize-none"
                  />
                </div>
              </div>

              <div className="flex flex-col h-full">
                {inputType === 'text' && (
                  <div className="flex-1 bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="font-semibold">课堂笔记</h4>
                      <button
                        onClick={handleAnalyze}
                        disabled={!summaryText.trim() || isAnalyzing}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs font-medium text-gray-400 hover:text-white hover:border-blue-500/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <Cpu size={13} className={isAnalyzing ? 'animate-pulse text-blue-400' : ''} />
                        {isAnalyzing ? '识别中...' : '识别'}
                      </button>
                    </div>
                    <textarea
                      placeholder="在此处粘贴您的课堂笔记或结构化大纲..."
                      value={summaryText}
                      onChange={(e) => setSummaryText(e.target.value)}
                      className="flex-1 bg-transparent border-none resize-none focus:outline-none text-gray-300 leading-relaxed font-mono text-sm min-h-[240px]"
                    />
                  </div>
                )}
                <button
                  onClick={handleGenerate}
                  className="mt-6 w-full bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-2xl font-bold text-lg shadow-xl shadow-blue-600/20 transition-all flex items-center justify-center gap-2"
                >
                  生成复习资料 PDF
                  <ArrowRight size={20} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const LibraryPage = () => {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<Lesson[]>('/api/lessons')
      .then(setLessons)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此课程？相关 PDF 也会被删除。')) return;
    await apiFetch(`/api/lessons/${id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-2xl font-bold">课程列表</h3>
        <div className="flex gap-2">
          <button className="p-2 bg-white/5 border border-white/10 rounded-xl text-gray-400 hover:text-white transition-all">
            <Filter size={20} />
          </button>
        </div>
      </div>

      <div className="bg-white/5 border border-white/10 rounded-3xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : lessons.length === 0 ? (
          <div className="p-8 text-center text-gray-500">暂无课程，点击「添加课程」开始记录。</div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-xs text-gray-500 uppercase tracking-wider">
                <th className="px-6 py-4 font-semibold">课程名称</th>
                <th className="px-6 py-4 font-semibold">科目 / 年级</th>
                <th className="px-6 py-4 font-semibold">日期</th>
                <th className="px-6 py-4 font-semibold">PDF</th>
                <th className="px-6 py-4 font-semibold text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {lessons.map((lesson) => (
                <tr key={lesson.id} className="hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-600/10 flex items-center justify-center text-blue-500">
                        <FileText size={16} />
                      </div>
                      <span className="font-medium">{lesson.topic || `${lesson.subject} 课程`}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      {lesson.subject && (
                        <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 text-[10px] font-bold uppercase">
                          {lesson.subject}
                        </span>
                      )}
                      {lesson.grade && (
                        <span className="px-2 py-0.5 rounded bg-white/10 text-gray-400 text-[10px] font-bold uppercase">
                          {lesson.grade}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 font-mono">{lesson.date}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-1.5 h-1.5 rounded-full ${lesson.pdf_path ? 'bg-green-500' : 'bg-gray-600'}`}
                      />
                      <span className="text-sm text-gray-500">{lesson.pdf_path ? '已生成' : '无'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {lesson.pdf_path && (
                        <>
                          <a
                            href={`/pdf/${lesson.id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all"
                            title="查看"
                          >
                            <Eye size={16} />
                          </a>
                          <a
                            href={`/pdf/download/${lesson.id}`}
                            className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-all"
                            title="下载"
                          >
                            <Download size={16} />
                          </a>
                        </>
                      )}
                      <button
                        onClick={() => handleDelete(lesson.id)}
                        className="p-2 hover:bg-red-500/10 rounded-lg text-gray-400 hover:text-red-500 transition-all"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

const QuestionBank = () => {
  const [data, setData] = useState<QuizData>({ total: 0, categories: {} });
  const [showAnswers, setShowAnswers] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<QuizData>('/api/quiz')
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const allQuestions: Question[] = (Object.values(data.categories) as Question[][]).flat();

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">题库浏览</h3>
          <p className="text-gray-500">浏览从课程中自动提取的填空题。共 {data.total} 道题。</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-xl">
            <span className="text-sm text-gray-400">显示答案</span>
            <button
              onClick={() => setShowAnswers(!showAnswers)}
              className={`w-10 h-5 rounded-full relative transition-colors ${showAnswers ? 'bg-blue-600' : 'bg-white/20'}`}
            >
              <motion.div
                animate={{ x: showAnswers ? 20 : 2 }}
                className="absolute top-1 w-3 h-3 bg-white rounded-full"
              />
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-500">加载中...</div>
      ) : allQuestions.length === 0 ? (
        <div className="p-8 text-center text-gray-500">暂无题目，添加课程后将自动提取填空题。</div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {allQuestions.map((item, i) => (
            <div
              key={item.id}
              className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-blue-500/30 transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-3 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded">
                      Q{i + 1}
                    </span>
                    {item.category && (
                      <span className="text-xs text-gray-500">{item.category}</span>
                    )}
                  </div>
                  <p className="text-lg text-gray-200 leading-relaxed">
                    {item.question.split('___').map((part, index, array) => (
                      <React.Fragment key={index}>
                        {part}
                        {index < array.length - 1 && (
                          <span
                            className={`inline-block border-b-2 border-blue-500/50 min-w-[80px] text-center px-2 font-bold transition-all ${
                              showAnswers ? 'text-blue-400 opacity-100' : 'text-transparent opacity-0'
                            }`}
                          >
                            {item.answer}
                          </span>
                        )}
                      </React.Fragment>
                    ))}
                  </p>
                  {showAnswers && !item.question.includes('___') && (
                    <p className="text-sm text-blue-400 mt-2">答案：{item.answer}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const ApprovalPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [items, setItems] = useState<RegistrationRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch<{ items: RegistrationRequestItem[] }>('/api/admin/registration-requests');
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems().catch(() => undefined);
  }, [loadItems]);

  const handleDecision = async (requestId: number, action: 'approve' | 'reject') => {
    setActingId(requestId);
    setError('');
    try {
      await apiFetch(`/api/admin/registration-requests/${requestId}/${action}`, {
        method: 'POST',
      });
      setItems((current) => current.filter((item) => item.id !== requestId));
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批操作失败');
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="p-8 space-y-8">
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)] gap-6">
        <section className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-5">
          <div>
            <p className="text-sm text-gray-500 uppercase tracking-[0.25em]">Owner</p>
            <h3 className="text-2xl font-bold mt-3">账号审批</h3>
            <p className="text-sm text-gray-400 mt-2">只有最高权限账号可以审核注册申请，并为用户开通后台访问权限。</p>
          </div>
          <div className="rounded-2xl border border-blue-500/20 bg-blue-500/10 p-5">
            <p className="text-xs text-blue-300 uppercase tracking-[0.25em]">Current Account</p>
            <p className="text-xl font-semibold mt-3">{currentUser.display_name}</p>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-500">用户名</span>
                <span>{currentUser.username}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-500">权限</span>
                <span>{getRoleLabel(currentUser.role)}</span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-500">机构</span>
                <span>{currentUser.organization_name}</span>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs text-gray-500 uppercase tracking-[0.25em]">Queue</p>
            <p className="text-4xl font-bold mt-3">{items.length}</p>
            <p className="text-sm text-gray-500 mt-2">当前待审核注册申请</p>
          </div>
        </section>

        <section className="bg-white/5 border border-white/10 rounded-3xl p-6">
          <div className="flex items-center justify-between gap-4 mb-6">
            <div>
              <h4 className="text-xl font-semibold">待审批申请</h4>
              <p className="text-sm text-gray-500 mt-1">新账号统一归属机构 {currentUser.organization_name}，通过后即可进入后台。</p>
            </div>
            <button
              onClick={() => loadItems().catch(() => undefined)}
              className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-sm font-medium transition-colors"
            >
              刷新列表
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center text-gray-500">正在读取审批队列...</div>
          ) : items.length === 0 ? (
            <div className="p-10 rounded-2xl border border-dashed border-white/10 text-center text-gray-500">
              暂无待审批申请，新的注册请求会出现在这里。
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item) => {
                const busy = actingId === item.id;
                return (
                  <div key={item.id} className="rounded-2xl border border-white/10 bg-black/20 p-5">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-lg font-semibold">{item.display_name}</span>
                          <span className="text-xs px-2.5 py-1 rounded-full border border-blue-500/20 bg-blue-500/10 text-blue-300">
                            待审批
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-gray-400">
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-gray-600">用户名</p>
                            <p className="text-gray-200 mt-1">{item.username}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-gray-600">机构</p>
                            <p className="text-gray-200 mt-1">{item.organization_name}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.2em] text-gray-600">申请时间</p>
                            <p className="text-gray-200 mt-1">{item.created_at}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleDecision(item.id, 'reject')}
                          disabled={busy}
                          className="px-4 py-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-60 transition-colors"
                        >
                          拒绝
                        </button>
                        <button
                          onClick={() => handleDecision(item.id, 'approve')}
                          disabled={busy}
                          className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 transition-colors font-semibold"
                        >
                          {busy ? '处理中...' : '通过并开通'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

const SettingsPage = ({ currentUser, onLogout }: { currentUser: CurrentUser; onLogout: () => void }) => {
  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <h3 className="text-2xl font-bold">系统设置</h3>

      <section className="space-y-4">
        <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">账号</h4>
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div>
            <p className="font-medium">当前账号</p>
            <p className="text-sm text-gray-500 mt-0.5">登出后需重新输入用户名和密码。</p>
            <div className="flex flex-wrap gap-2 mt-4 text-xs">
              <span className="px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300">
                {currentUser.display_name}
              </span>
              <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-gray-300">
                {getRoleLabel(currentUser.role)}
              </span>
              <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-gray-300">
                {currentUser.organization_name}
              </span>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-sm font-semibold transition-all"
          >
            退出登录
          </button>
        </div>
      </section>

      <section className="space-y-4">
        <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">关于</h4>
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">产品</span>
            <span>星润课后复习系统</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">版本</span>
            <span className="font-mono">v1.0.0</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">AI 引擎</span>
            <span>由星润提供</span>
          </div>
        </div>
      </section>
    </div>
  );
};

// --- Login Modal ---

const LoginModal = ({
  onLogin,
  onClose,
  onOpenRegister,
}: {
  onLogin: (token: string) => void;
  onClose: () => void;
  onOpenRegister: () => void;
}) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string; token?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '登录服务不可用，请确认后端已启动');
      }
      onLogin(data.token);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">登录账号</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="请输入用户名"
                className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">密码</label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="请输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                >
                  {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <button
            type="button"
            onClick={onOpenRegister}
            className="w-full mt-4 py-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
          >
            还没有账号？提交注册申请
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};

const RegisterRequestModal = ({ onClose }: { onClose: () => void }) => {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/register-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          display_name: displayName,
          password,
          organization_name: '星润Starain',
        }),
      });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '注册申请提交失败');
      }
      setSuccess('申请已提交，等待 Kayn 审批通过后即可登录后台。');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册申请提交失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-lg"
      >
        <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold">提交注册申请</h2>
              <p className="text-sm text-gray-500 mt-1">所有新账号默认加入机构 星润Starain，审批通过后才能进入后台。</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/20 rounded-xl text-green-300 text-sm">
              <CheckCircle2 size={16} />
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">用户名</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="登录时使用"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">显示名</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="后台展示名称"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm text-gray-400">机构</label>
              <div className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-gray-200">
                星润Starain
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">密码</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    placeholder="至少 6 位"
                    className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 pr-11 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm text-gray-400">确认密码</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="再次输入密码"
                  className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white py-3 rounded-xl font-semibold transition-all shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? '提交中...' : '提交注册申请'}
            </button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

// --- Landing Page ---

const LandingPage = ({
  onLogin,
  onRegister,
}: {
  onLogin: () => void;
  onRegister: () => void;
}) => {
  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="星润 logo" className="w-12 h-12 object-contain" />
            <span className="text-xl font-bold tracking-tight">星润 AI 教育解决方案</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-400">
            <a href="#features" className="hover:text-white transition-colors">核心方案</a>
            <a href="#process" className="hover:text-white transition-colors">落地流程</a>
            <a href="#about" className="hover:text-white transition-colors">关于星润</a>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onRegister}
              className="hidden sm:inline-flex bg-white/5 border border-white/10 text-white px-5 py-2.5 rounded-full font-semibold text-sm hover:bg-white/10 transition-all active:scale-95"
            >
              申请注册
            </button>
            <button
              onClick={onLogin}
              className="bg-white text-black px-6 py-2.5 rounded-full font-bold text-sm hover:bg-gray-200 transition-all active:scale-95"
            >
              立即登录
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Background Video */}
        <div className="absolute inset-0 z-0">
          <video
            autoPlay
            loop
            muted
            playsInline
            className="w-full h-full object-cover opacity-30"
          >
            <source src="/bg.mp4" type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-b from-black via-transparent to-black" />
          <div className="absolute inset-0 bg-black/40" />
        </div>

        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/10 blur-[120px] rounded-full" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/10 blur-[120px] rounded-full" />
        </div>

        <div className="max-w-7xl mx-auto px-6 relative z-10 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 2, y: -100 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="inline-flex items-center rounded-full border border-blue-500/20 bg-blue-500/10 px-4 py-1.5 text-xs font-semibold tracking-[0.3em] text-blue-300 mb-6">
              AI EDU SOLUTION FOR TEAMS
            </span>
            <h1 className="mt-6 text-[13vw] md:text-[6.8vw] font-black leading-[0.9] tracking-tighter mb-8">
              为学校与教育机构打造
              <br />
              <span className="text-blue-500">可落地的 AI 教学方案</span>
            </h1>
          </motion.div>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.8 }}
            className="text-lg md:text-2xl text-gray-400 max-w-3xl mx-auto mb-12 font-light leading-relaxed"
          >
            以课后复习系统为落地起点，延展智能错题本、国际课程题库与自动组卷、
            教案讲义生成等核心模块，帮助教学团队建立更高效的内容生产与交付链路。
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.8 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <button
              onClick={onLogin}
              className="w-full sm:w-auto bg-blue-600 text-white px-10 py-5 rounded-2xl font-bold text-lg hover:bg-blue-500 transition-all shadow-[0_0_40px_rgba(59,130,246,0.3)] active:scale-95 flex items-center justify-center gap-2"
            >
              进入工作台
              <ArrowRight size={20} />
            </button>
            <a
              href="#features"
              className="w-full sm:w-auto bg-white/5 border border-white/10 text-white px-10 py-5 rounded-2xl font-bold text-lg hover:bg-white/10 transition-all active:scale-95 flex items-center justify-center gap-2"
            >
              查看方案版图
              <ArrowRight size={20} />
            </a>
          </motion.div>
        </div>
      </section>

      {/* Feature Bento Grid */}
      <section id="features" className="py-24 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">重构 AI 教学交付</h2>
            <p className="text-gray-500 text-lg">从单点工具走向可扩展的教育解决方案版图。</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Large Card */}
            <div className="md:col-span-2 bg-white/5 border border-white/10 rounded-[2.5rem] p-10 relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                <FileText size={200} />
              </div>
              <div className="relative z-10 h-full flex flex-col justify-between">
                <div>
                  <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mb-6">
                    <FileText size={24} />
                  </div>
                  <h3 className="text-3xl font-bold mb-4">课后复习系统</h3>
                  <p className="text-gray-400 text-lg max-w-2xl">
                    从课堂录音、笔记到结构化复习资料与题目生成，已经形成可落地的教学交付闭环。
                  </p>
                </div>
                <div className="mt-12 flex flex-wrap gap-4">
                  <div className="px-4 py-2 bg-white/5 rounded-full text-xs font-mono text-blue-400 border border-blue-500/20">课堂分析</div>
                  <div className="px-4 py-2 bg-white/5 rounded-full text-xs font-mono text-blue-400 border border-blue-500/20">复习资料生成</div>
                  <div className="px-4 py-2 bg-white/5 rounded-full text-xs font-mono text-blue-400 border border-blue-500/20">教学交付</div>
                </div>
              </div>
            </div>

            {/* Small Card */}
            <div className="bg-gradient-to-br from-purple-600/20 to-transparent border border-purple-500/20 rounded-[2.5rem] p-10 flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 bg-purple-600 rounded-2xl flex items-center justify-center mb-6">
                  <AlertCircle size={24} />
                </div>
                <h3 className="text-2xl font-bold mb-4">智能错题本</h3>
                <p className="text-gray-400">
                  沉淀学生高频错误与知识薄弱点，形成可持续追踪的个性化复习资产。
                </p>
              </div>
              <div className="mt-8 flex flex-wrap gap-2">
                <span className="text-[10px] bg-white/10 px-2 py-1 rounded tracking-widest font-bold">错因沉淀</span>
                <span className="text-[10px] bg-white/10 px-2 py-1 rounded tracking-widest font-bold">薄弱点追踪</span>
                <span className="text-[10px] bg-white/10 px-2 py-1 rounded tracking-widest font-bold">个性化复习</span>
              </div>
            </div>

            {/* Small Card */}
            <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-10 flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 bg-green-600 rounded-2xl flex items-center justify-center mb-6">
                  <Database size={24} />
                </div>
                <h3 className="text-2xl font-bold mb-4">国际课程题库 / 自动组卷</h3>
                <p className="text-gray-400">
                  面向 AP、A-Level、IB 等国际课程场景，支持题库沉淀、标签化管理与自动组卷。
                </p>
              </div>
              <div className="mt-8 flex items-center gap-2 text-green-500 font-bold text-sm">
                <span>AP / A-Level / IB</span>
                <ArrowRight size={14} />
              </div>
            </div>

            {/* Medium Card */}
            <div className="md:col-span-2 bg-white/5 border border-white/10 rounded-[2.5rem] p-10 flex flex-col md:flex-row gap-10 items-center">
              <div className="flex-1">
                <div className="w-12 h-12 bg-orange-600 rounded-2xl flex items-center justify-center mb-6">
                  <FileText size={24} />
                </div>
                <h3 className="text-3xl font-bold mb-4">教案与讲义生成</h3>
                <p className="text-gray-400 text-lg">
                  将课程目标、知识结构与教学素材快速转化为讲义、课堂提纲和教研交付内容。
                </p>
              </div>
              <div className="w-full md:w-72 bg-black border border-white/10 rounded-3xl p-5 flex flex-col gap-3">
                {[
                  { label: '讲义大纲', tone: 'bg-orange-500' },
                  { label: '课堂提纲', tone: 'bg-orange-400' },
                  { label: '教研材料', tone: 'bg-orange-300' },
                ].map((item, index) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0.4, x: 10 }}
                    animate={{ opacity: [0.5, 1, 0.7], x: [10, 0, 4] }}
                    transition={{ duration: 2.2, delay: index * 0.2, repeat: Infinity }}
                    className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-white">{item.label}</span>
                      <span className="text-[10px] rounded-full border border-white/10 bg-white/5 px-2 py-1 text-gray-400">
                        AI Draft
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                        <motion.div
                          animate={{ width: ['18%', '72%', '48%'] }}
                          transition={{ duration: 2.2, delay: index * 0.2, repeat: Infinity }}
                          className={`h-full ${item.tone}`}
                        />
                      </div>
                      <div className="h-2 w-3/4 rounded-full bg-white/10" />
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Process Section */}
      <section id="process" className="py-24 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-bold mb-16">三步搭建 AI 教学交付链路</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 relative">
            <div className="hidden md:block absolute top-1/2 left-0 w-full h-[1px] bg-white/10 -translate-y-1/2 z-0"></div>
            {[
              { step: '01', title: '教学素材接入', desc: '接入课堂录音、笔记、题目与课程资料。' },
              { step: '02', title: 'AI 模块处理', desc: '按复习、错题、组卷、讲义等场景完成结构化生成。' },
              { step: '03', title: '面向团队交付', desc: '输出给教师、教研与教学运营团队，形成标准化内容资产。' },
            ].map((item, i) => (
              <div key={i} className="relative z-10 flex flex-col items-center">
                <div className="w-20 h-20 bg-black border border-white/20 rounded-full flex items-center justify-center text-2xl font-black mb-6 shadow-2xl">
                  {item.step}
                </div>
                <h4 className="text-xl font-bold mb-2">{item.title}</h4>
                <p className="text-gray-500 max-w-[200px]">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer id="about" className="py-20 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex flex-col items-center md:items-start gap-3">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="星润 logo" className="w-10 h-10 object-contain" />
              <span className="text-lg font-bold tracking-tight">星润 AI 教育解决方案</span>
            </div>
            <p className="max-w-md text-sm text-gray-500 text-center md:text-left">
              面向学校、机构与教学团队，构建从内容生成到教学交付的 AI 能力底座。
            </p>
          </div>
          <p className="text-gray-600 text-sm">© 2026 Xingrun AI. All rights reserved.</p>
          <div className="flex gap-6 text-gray-500 text-sm">
            <a href="#" className="hover:text-white">隐私政策</a>
            <a href="#" className="hover:text-white">服务条款</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

// --- Main App ---

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem('xr_token') || '');
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authReady, setAuthReady] = useState<boolean>(() => !Boolean(localStorage.getItem('xr_token')));
  const [showLogin, setShowLogin] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [activePage, setActivePage] = useState<Page>('dashboard');
  const [showLanding, setShowLanding] = useState(false);

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setAuthReady(true);
      return;
    }

    let cancelled = false;
    setAuthReady(false);

    apiFetch<CurrentUser>('/api/me')
      .then((user) => {
        if (cancelled) {
          return;
        }
        setCurrentUser(user);
        setActivePage((page) => (page === 'accounts' && user.role !== 'owner' ? 'dashboard' : page));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        localStorage.removeItem('xr_token');
        setToken('');
        setCurrentUser(null);
      })
      .finally(() => {
        if (!cancelled) {
          setAuthReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleLogin = (t: string) => {
    localStorage.setItem('xr_token', t);
    setToken(t);
    setShowLogin(false);
    setShowLanding(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('xr_token');
    setToken('');
    setCurrentUser(null);
    setShowLanding(false);
    setActivePage('dashboard');
  };

  const handleLessonSuccess = () => {
    setActivePage('library');
  };

  const pageTitle: Record<Page, string> = {
    dashboard: '工作台',
    input: '添加课程',
    library: '课程列表',
    questions: '题库浏览',
    accounts: '账号审批',
    settings: '系统设置',
  };

  if (token && !authReady) {
    return (
      <div className="min-h-screen bg-black text-gray-100 flex items-center justify-center px-6">
        <div className="w-full max-w-xl rounded-[2rem] border border-white/10 bg-white/5 p-8">
          <XiaojimaoLoading label="正在验证账号权限..." />
        </div>
      </div>
    );
  }

  if (!token || !currentUser || showLanding) {
    return (
      <>
        <LandingPage
          onLogin={token ? () => setShowLanding(false) : () => setShowLogin(true)}
          onRegister={() => {
            if (token) {
              setShowLanding(false);
              return;
            }
            setShowRegister(true);
          }}
        />
        <AnimatePresence>
          {showLogin && (
            <LoginModal
              onLogin={handleLogin}
              onClose={() => setShowLogin(false)}
              onOpenRegister={() => {
                setShowLogin(false);
                setShowRegister(true);
              }}
            />
          )}
          {showRegister && (
            <RegisterRequestModal onClose={() => setShowRegister(false)} />
          )}
        </AnimatePresence>
      </>
    );
  }

  return (
    <div className="flex min-h-screen bg-black text-gray-100">
      <Sidebar activePage={activePage} currentUser={currentUser} setActivePage={setActivePage} />
      <main className="flex-1 flex flex-col">
        <Header title={pageTitle[activePage]} onGoHome={() => setShowLanding(true)} />
        <div className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={activePage}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
            >
              {activePage === 'dashboard' && <Dashboard currentUser={currentUser} setActivePage={setActivePage} />}
              {activePage === 'input' && <LessonInput onSuccess={handleLessonSuccess} />}
              {activePage === 'library' && <LibraryPage />}
              {activePage === 'questions' && <QuestionBank />}
              {activePage === 'accounts' && currentUser.role === 'owner' && <ApprovalPage currentUser={currentUser} />}
              {activePage === 'settings' && <SettingsPage currentUser={currentUser} onLogout={handleLogout} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
