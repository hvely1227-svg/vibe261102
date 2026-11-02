// 진입점: 초기 상태 구성, 이벤트 바인딩
import { addDays, todayKey } from './date.js';
import { reducer, sanitizeTodos } from './todo.js';
import { createStore, loadPersisted } from './store.js';
import { render } from './render.js';

const UNDO_MS = 5000;
const $ = (id) => document.getElementById(id);

const els = {
  title: $('title'),
  themeToggle: $('theme-toggle'),
  prevDay: $('prev-day'),
  nextDay: $('next-day'),
  goToday: $('go-today'),
  date: $('date'),
  progressBar: $('progress-bar'),
  progressFill: $('progress-fill'),
  progressText: $('progress-text'),
  celebrate: $('celebrate'),
  storageNotice: $('storage-notice'),
  carryBanner: $('carry-banner'),
  carryText: $('carry-text'),
  carryAccept: $('carry-accept'),
  carryDismiss: $('carry-dismiss'),
  composer: $('composer'),
  newTodo: $('new-todo'),
  newTag: $('new-tag'),
  readonlyNote: $('readonly-note'),
  filterButtons: [...document.querySelectorAll('[data-filter]')],
  list: $('todo-list'),
  empty: $('empty'),
  remaining: $('remaining'),
  clearDone: $('clear-done'),
  exportButton: $('export-btn'),
  importButton: $('import-btn'),
  importFile: $('import-file'),
  toast: $('toast'),
  toastText: $('toast-text'),
  undoButton: $('undo-btn'),
};

const { data, storage } = loadPersisted();
const today = todayKey();
const store = createStore(
  reducer,
  { todos: data.todos, settings: data.settings, today, viewDate: today, filter: 'all', lastRemoved: null },
  storage,
);

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
const ui = {
  editingId: null,
  draft: '',
  focus: null, // 다시 그린 뒤 포커스를 돌려줄 대상 { id, selector }
  systemDark: darkQuery.matches,
  notice: !data.persistent
    ? data.recovered
      ? '저장된 데이터를 읽지 못했고 저장소도 쓸 수 없어요. 새로고침하면 내용이 사라져요.'
      : '이 브라우저에서는 저장소를 쓸 수 없어 새로고침하면 내용이 사라져요.'
    : data.recovered
      ? '저장된 데이터를 읽지 못해 새로 시작했어요. 기존 데이터는 백업해 두었어요.'
      : '',
};

function applyTheme(theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

function rerender() {
  const state = store.getState();
  // 목록을 통째로 다시 그리므로, 별도 지정이 없으면 현재 포커스 위치를 기억해 둔다.
  if (!ui.focus) ui.focus = currentListFocus();
  applyTheme(state.settings.theme);
  render(state, els, ui);
  restoreFocus();
}

function currentListFocus() {
  const active = document.activeElement;
  const item = active?.closest?.('li.todo');
  if (!item || !els.list.contains(item)) return null;
  if (active === item) return { id: item.dataset.id };
  if (active.dataset.action) return { id: item.dataset.id, selector: `[data-action="${active.dataset.action}"]` };
  return { id: item.dataset.id };
}

function restoreFocus() {
  const target = ui.focus;
  ui.focus = null;
  if (!target) return;
  if (target === 'input') return els.newTodo.focus();
  const item = els.list.querySelector(`li[data-id="${CSS.escape(target.id)}"]`);
  const node = item && ((target.selector && item.querySelector(target.selector)) || item);
  if (!node) return;
  node.focus();
  if (node.classList.contains('edit-input')) node.setSelectionRange(node.value.length, node.value.length);
}

// 페이지를 연 채 자정을 넘긴 경우를 위해 조작 전마다 오늘 날짜를 다시 계산한다.
function refreshToday() {
  store.dispatch({ type: 'SET_TODAY', today: todayKey() });
}

function act(action) {
  refreshToday();
  store.dispatch(action);
}

let undoTimer = null;
store.subscribe((state, prev) => {
  if (state.lastRemoved !== prev.lastRemoved) {
    clearTimeout(undoTimer);
    if (state.lastRemoved) undoTimer = setTimeout(() => store.dispatch({ type: 'DISMISS_UNDO' }), UNDO_MS);
  }
  if (ui.editingId && !state.todos.some((t) => t.id === ui.editingId && t.date === state.today)) {
    ui.editingId = null;
  }
  rerender();
});

// ── 입력 ──
els.composer.addEventListener('submit', (event) => {
  event.preventDefault();
  act({ type: 'ADD', text: els.newTodo.value, tag: els.newTag.value });
  els.newTodo.value = '';
  els.newTodo.focus();
});

// ── 항목 조작 ──
function itemId(node) {
  return node.closest('li.todo')?.dataset.id;
}

function startEdit(id) {
  const todo = store.getState().todos.find((t) => t.id === id);
  if (!todo || todo.date !== store.getState().today) return;
  ui.editingId = id;
  ui.draft = todo.text;
  ui.focus = { id, selector: '.edit-input' };
  rerender();
}

function finishEdit(save) {
  const id = ui.editingId;
  if (!id) return;
  const text = ui.draft;
  ui.editingId = null;
  ui.focus = { id };
  if (save) act({ type: 'EDIT', id, text });
  rerender();
}

function deleteItem(id) {
  // 삭제 후 다음 항목(없으면 이전 항목, 그것도 없으면 입력창)으로 포커스 이동
  const items = [...els.list.querySelectorAll('li.todo')];
  const index = items.findIndex((li) => li.dataset.id === id);
  const neighbor = items[index + 1] || items[index - 1];
  ui.focus = neighbor ? { id: neighbor.dataset.id } : 'input';
  act({ type: 'DELETE', id });
}

els.list.addEventListener('change', (event) => {
  if (event.target.dataset.action !== 'toggle') return;
  const id = itemId(event.target);
  ui.focus = { id, selector: '.check' };
  act({ type: 'TOGGLE', id });
});

els.list.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const id = itemId(button);
  if (button.dataset.action === 'important') {
    ui.focus = { id, selector: '.star' };
    act({ type: 'TOGGLE_IMPORTANT', id });
  } else if (button.dataset.action === 'edit') {
    startEdit(id);
  } else if (button.dataset.action === 'delete') {
    deleteItem(id);
  }
});

els.list.addEventListener('dblclick', (event) => {
  if (event.target.closest('.todo-text')) startEdit(itemId(event.target));
});

els.list.addEventListener('input', (event) => {
  if (event.target.classList.contains('edit-input')) ui.draft = event.target.value;
});

els.list.addEventListener('keydown', (event) => {
  if (event.target.classList.contains('edit-input')) {
    if (event.isComposing) return; // 한글 조합 중 Enter 무시
    if (event.key === 'Enter') {
      event.preventDefault();
      finishEdit(true);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      finishEdit(false);
    }
    return;
  }
  if (!event.target.matches('li.todo')) return;
  const id = event.target.dataset.id;
  if (store.getState().viewDate !== store.getState().today) return;
  if (event.key === ' ') {
    event.preventDefault();
    ui.focus = { id };
    act({ type: 'TOGGLE', id });
  } else if (event.key === 'Enter') {
    event.preventDefault();
    startEdit(id);
  } else if (event.key === 'Delete') {
    event.preventDefault();
    deleteItem(id);
  }
});

els.list.addEventListener('focusout', (event) => {
  if (event.target.classList.contains('edit-input') && ui.editingId) finishEdit(true);
});

// ── 드래그 앤 드롭 순서 변경 (전체 필터에서만) ──
let dragging = null;

els.list.addEventListener('dragstart', (event) => {
  const li = event.target.closest?.('li.todo');
  if (!li || !li.draggable) return;
  dragging = li;
  li.classList.add('dragging');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', li.dataset.id);
});

els.list.addEventListener('dragover', (event) => {
  if (!dragging) return;
  event.preventDefault();
  const over = event.target.closest('li.todo');
  if (!over || over === dragging) return;
  const rect = over.getBoundingClientRect();
  const after = event.clientY > rect.top + rect.height / 2;
  over.parentNode.insertBefore(dragging, after ? over.nextSibling : over);
});

els.list.addEventListener('drop', (event) => {
  if (dragging) event.preventDefault();
});

els.list.addEventListener('dragend', (event) => {
  if (!dragging) return;
  const id = dragging.dataset.id;
  dragging.classList.remove('dragging');
  dragging = null;
  if (event.dataTransfer.dropEffect === 'none') return rerender(); // 취소 시 원위치
  const ids = [...els.list.querySelectorAll('li.todo')].map((li) => li.dataset.id);
  ui.focus = { id };
  act({ type: 'REORDER', ids });
});

// ── 필터·날짜·이월·테마 ──
els.filterButtons.forEach((button) =>
  button.addEventListener('click', () => act({ type: 'SET_FILTER', filter: button.dataset.filter })),
);

els.prevDay.addEventListener('click', () => act({ type: 'SET_VIEW_DATE', date: addDays(store.getState().viewDate, -1) }));
els.nextDay.addEventListener('click', () => act({ type: 'SET_VIEW_DATE', date: addDays(store.getState().viewDate, 1) }));
els.goToday.addEventListener('click', () => act({ type: 'SET_VIEW_DATE', date: store.getState().today }));

els.carryAccept.addEventListener('click', () => act({ type: 'CARRY_OVER' }));
els.carryDismiss.addEventListener('click', () => act({ type: 'DISMISS_CARRY_OVER' }));

els.themeToggle.addEventListener('click', () => {
  const { theme } = store.getState().settings;
  const dark = theme === 'dark' || (theme === 'system' && ui.systemDark);
  act({ type: 'SET_THEME', theme: dark ? 'light' : 'dark' });
});

darkQuery.addEventListener('change', (event) => {
  ui.systemDark = event.matches;
  rerender();
});

// ── 완료 항목 지우기 / 실행 취소 ──
els.clearDone.addEventListener('click', () => act({ type: 'CLEAR_DONE' }));
els.undoButton.addEventListener('click', () => act({ type: 'UNDO_REMOVE' }));

// ── 내보내기 / 가져오기 ──
els.exportButton.addEventListener('click', () => {
  const { todos } = store.getState();
  const payload = JSON.stringify({ app: 'todolist', version: 1, exportedAt: new Date().toISOString(), todos }, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `todolist-backup-${todayKey()}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
});

els.importButton.addEventListener('click', () => els.importFile.click());

els.importFile.addEventListener('change', async () => {
  const file = els.importFile.files[0];
  els.importFile.value = '';
  if (!file) return;
  let todos = null;
  try {
    const parsed = JSON.parse(await file.text());
    todos = sanitizeTodos(Array.isArray(parsed) ? parsed : parsed?.todos);
  } catch {
    todos = null;
  }
  if (!todos) {
    window.alert('올바른 백업 파일이 아니에요.');
    return;
  }
  const current = store.getState().todos.length;
  if (window.confirm(`현재 할 일 ${current}개를 백업 파일의 ${todos.length}개로 바꿀까요?`)) {
    act({ type: 'IMPORT', todos });
  }
});

// ── 전역 단축키: / 또는 n → 입력창 ──
document.addEventListener('keydown', (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
  if (event.target.closest('input, textarea, select, [contenteditable="true"]')) return;
  if ((event.key === '/' || event.key === 'n') && !els.composer.hidden) {
    event.preventDefault();
    els.newTodo.focus();
  }
});

// ── 자정 넘김 처리 ──
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshToday();
});
window.addEventListener('focus', refreshToday);
setInterval(refreshToday, 60_000);

rerender();
