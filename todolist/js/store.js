// 상태 저장소 + localStorage 입출력
import { sanitizeSettings, sanitizeTodos } from './todo.js';

export const KEYS = {
  todos: 'todolist:v1:todos',
  settings: 'todolist:v1:settings',
  backup: 'todolist:v1:backup',
};

// 시크릿 모드 등에서 localStorage 접근이 막히면 null (메모리 모드)
function getStorage() {
  try {
    const storage = window.localStorage;
    const probe = 'todolist:probe';
    storage.setItem(probe, '1');
    storage.removeItem(probe);
    return storage;
  } catch {
    return null;
  }
}

function readJSON(storage, key) {
  const raw = storage.getItem(key);
  if (raw === null) return { raw, value: undefined };
  try {
    return { raw, value: JSON.parse(raw) };
  } catch {
    return { raw, value: null };
  }
}

export function loadPersisted() {
  const storage = getStorage();
  const data = { todos: [], settings: sanitizeSettings(null), persistent: Boolean(storage), recovered: false };
  if (!storage) return { data, storage };

  const todos = readJSON(storage, KEYS.todos);
  if (todos.raw !== null) {
    const parsed = sanitizeTodos(todos.value);
    if (parsed) {
      data.todos = parsed;
    } else {
      // 파싱 실패: 원본을 백업 키에 보존하고 빈 목록으로 시작
      try {
        storage.setItem(KEYS.backup, todos.raw);
      } catch {
        // 백업도 실패하면 원본 키를 덮어쓰지 않도록 저장을 끈다
        return { data: { ...data, persistent: false, recovered: true }, storage: null };
      }
      data.recovered = true;
    }
  }
  data.settings = sanitizeSettings(readJSON(storage, KEYS.settings).value);
  return { data, storage };
}

export function createStore(reducer, initialState, storage) {
  let state = initialState;
  const listeners = new Set();

  function persist(prev) {
    if (!storage) return;
    try {
      if (prev.todos !== state.todos) storage.setItem(KEYS.todos, JSON.stringify(state.todos));
      if (prev.settings !== state.settings) storage.setItem(KEYS.settings, JSON.stringify(state.settings));
    } catch (error) {
      console.warn('할 일을 저장하지 못했어요.', error);
    }
  }

  return {
    getState: () => state,
    dispatch(action) {
      const prev = state;
      state = reducer(state, action);
      if (state === prev) return;
      persist(prev);
      listeners.forEach((listener) => listener(state, prev));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
