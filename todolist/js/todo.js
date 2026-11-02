// Todo 생성/정렬/필터/이월 로직과 리듀서. DOM·저장소에 의존하지 않는 순수 함수만 둔다.
import { isValidKey } from './date.js';

export const MAX_LENGTH = 100;
export const FILTERS = ['all', 'active', 'done'];
export const TAGS = ['morning', 'afternoon', 'evening'];
export const TAG_LABELS = { morning: '오전', afternoon: '오후', evening: '저녁' };
export const THEMES = ['system', 'light', 'dark'];

export function newId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

// 앞뒤 공백 제거 후 100자로 자른다. 빈 문자열이면 null.
export function normalizeText(raw) {
  if (typeof raw !== 'string') return null;
  const text = raw.trim().slice(0, MAX_LENGTH);
  return text || null;
}

export function createTodo({ text, date, order, tag = null, now = Date.now() }) {
  return { id: newId(), text, done: false, important: false, tag, date, order, createdAt: now };
}

export function todosForDate(todos, date) {
  return todos.filter((t) => t.date === date);
}

// 중요(★) 우선 → 미완료 우선 → order 오름차순
export function sortTodos(list) {
  return [...list].sort(
    (a, b) => Number(b.important) - Number(a.important) || Number(a.done) - Number(b.done) || a.order - b.order,
  );
}

export function filterTodos(list, filter) {
  if (filter === 'active') return list.filter((t) => !t.done);
  if (filter === 'done') return list.filter((t) => t.done);
  return list;
}

export function progress(list) {
  const done = list.filter((t) => t.done).length;
  return { done, total: list.length };
}

// 마지막으로 이월 여부를 결정한 날 이후의 미완료 항목만 제안한다.
// (한 번 "무시"한 항목이 매일 다시 뜨지 않도록)
export function carryOverCandidates(todos, today, lastVisitDate) {
  return todos.filter((t) => !t.done && t.date < today && (!lastVisitDate || t.date >= lastVisitDate));
}

export function shouldOfferCarryOver(state) {
  if (state.settings.lastVisitDate === state.today) return false;
  return carryOverCandidates(state.todos, state.today, state.settings.lastVisitDate).length > 0;
}

function nextOrder(todos, date) {
  return todosForDate(todos, date).reduce((max, t) => Math.max(max, t.order), -1) + 1;
}

// 저장소·가져오기 파일에서 읽은 값을 검증한다. 배열이 아니면 null.
export function sanitizeTodos(raw) {
  if (!Array.isArray(raw)) return null;
  const seen = new Set();
  const result = [];
  raw.forEach((item, i) => {
    if (!item || typeof item !== 'object') return;
    const text = normalizeText(item.text);
    if (!text || !isValidKey(item.date)) return;
    const id = typeof item.id === 'string' && item.id && !seen.has(item.id) ? item.id : newId();
    seen.add(id);
    const todo = {
      id,
      text,
      done: Boolean(item.done),
      important: Boolean(item.important),
      tag: TAGS.includes(item.tag) ? item.tag : null,
      date: item.date,
      order: Number.isFinite(item.order) ? item.order : i,
      createdAt: Number.isFinite(item.createdAt) ? item.createdAt : Date.now(),
    };
    if (todo.done && Number.isFinite(item.completedAt)) todo.completedAt = item.completedAt;
    result.push(todo);
  });
  return result;
}

export function sanitizeSettings(raw) {
  const settings = { theme: 'system', lastVisitDate: null };
  if (raw && typeof raw === 'object') {
    if (THEMES.includes(raw.theme)) settings.theme = raw.theme;
    if (isValidKey(raw.lastVisitDate)) settings.lastVisitDate = raw.lastVisitDate;
  }
  return settings;
}

// 오늘 날짜의 항목만 변경할 수 있다. 지난 날짜는 읽기 전용.
function updateTodo(state, id, update) {
  let changed = false;
  const todos = state.todos.map((t) => {
    if (t.id !== id || t.date !== state.today) return t;
    changed = true;
    return update(t);
  });
  return changed ? { ...state, todos } : state;
}

export function reducer(state, action) {
  switch (action.type) {
    case 'ADD': {
      const text = normalizeText(action.text);
      if (!text) return state;
      const tag = TAGS.includes(action.tag) ? action.tag : null;
      const todo = createTodo({ text, date: state.today, order: nextOrder(state.todos, state.today), tag });
      return { ...state, todos: [...state.todos, todo] };
    }
    case 'TOGGLE':
      return updateTodo(state, action.id, (t) => {
        if (t.done) {
          const { completedAt, ...rest } = t;
          return { ...rest, done: false };
        }
        return { ...t, done: true, completedAt: Date.now() };
      });
    case 'EDIT': {
      const text = normalizeText(action.text);
      if (!text) return state;
      return updateTodo(state, action.id, (t) => (t.text === text ? t : { ...t, text }));
    }
    case 'TOGGLE_IMPORTANT':
      return updateTodo(state, action.id, (t) => ({ ...t, important: !t.important }));
    case 'DELETE': {
      const target = state.todos.find((t) => t.id === action.id && t.date === state.today);
      if (!target) return state;
      return { ...state, todos: state.todos.filter((t) => t !== target), lastRemoved: [target] };
    }
    case 'CLEAR_DONE': {
      const removed = state.todos.filter((t) => t.date === state.today && t.done);
      if (!removed.length) return state;
      return { ...state, todos: state.todos.filter((t) => !removed.includes(t)), lastRemoved: removed };
    }
    case 'UNDO_REMOVE':
      if (!state.lastRemoved) return state;
      return { ...state, todos: [...state.todos, ...state.lastRemoved], lastRemoved: null };
    case 'DISMISS_UNDO':
      return state.lastRemoved ? { ...state, lastRemoved: null } : state;
    case 'REORDER': {
      const index = new Map(action.ids.map((id, i) => [id, i]));
      return {
        ...state,
        todos: state.todos.map((t) => (index.has(t.id) && t.date === state.today ? { ...t, order: index.get(t.id) } : t)),
      };
    }
    case 'CARRY_OVER': {
      const ids = new Set(carryOverCandidates(state.todos, state.today, state.settings.lastVisitDate).map((t) => t.id));
      let order = nextOrder(state.todos, state.today);
      return {
        ...state,
        todos: state.todos.map((t) => (ids.has(t.id) ? { ...t, date: state.today, order: order++ } : t)),
        settings: { ...state.settings, lastVisitDate: state.today },
      };
    }
    case 'DISMISS_CARRY_OVER':
      return { ...state, settings: { ...state.settings, lastVisitDate: state.today } };
    case 'SET_FILTER':
      return FILTERS.includes(action.filter) ? { ...state, filter: action.filter } : state;
    case 'SET_THEME':
      return THEMES.includes(action.theme) ? { ...state, settings: { ...state.settings, theme: action.theme } } : state;
    case 'SET_VIEW_DATE': {
      if (!isValidKey(action.date) || action.date > state.today || action.date === state.viewDate) return state;
      return { ...state, viewDate: action.date };
    }
    case 'SET_TODAY': {
      if (action.today === state.today) return state;
      // 오늘을 보고 있었다면 새 오늘로 따라간다.
      const viewDate = state.viewDate === state.today ? action.today : state.viewDate;
      return { ...state, today: action.today, viewDate };
    }
    case 'IMPORT':
      return { ...state, todos: action.todos, lastRemoved: null };
    default:
      return state;
  }
}
