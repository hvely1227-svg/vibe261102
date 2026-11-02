// state → DOM. 사용자 입력은 항상 textContent/value로 넣어 XSS를 막는다.
import { formatKorean } from './date.js';
import {
  TAG_LABELS,
  carryOverCandidates,
  filterTodos,
  progress,
  shouldOfferCarryOver,
  sortTodos,
  todosForDate,
} from './todo.js';

const EMPTY_MESSAGES = {
  all: '오늘 할 일을 추가해보세요 ✏️',
  active: '진행 중인 할 일이 없어요',
  done: '완료된 할 일이 없어요',
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function iconButton(action, label, glyph, className = '') {
  const button = el('button', `icon-btn ${className}`.trim(), glyph);
  button.type = 'button';
  button.dataset.action = action;
  button.setAttribute('aria-label', label);
  button.title = label;
  return button;
}

function renderItem(todo, { readonly, draggable, editing, draft }) {
  const li = el('li', 'todo');
  li.dataset.id = todo.id;
  li.tabIndex = 0;
  li.classList.toggle('is-done', todo.done);
  li.classList.toggle('is-important', todo.important);
  li.setAttribute('aria-label', `${todo.text}${todo.done ? ', 완료됨' : ''}${todo.important ? ', 중요' : ''}`);

  if (draggable && !editing) {
    li.draggable = true;
    li.append(el('span', 'drag-handle', '⠿'));
    li.lastChild.setAttribute('aria-hidden', 'true');
  }

  const check = el('input', 'check');
  check.type = 'checkbox';
  check.checked = todo.done;
  check.disabled = readonly;
  check.dataset.action = 'toggle';
  check.setAttribute('aria-label', `"${todo.text}" 완료`);
  li.append(check);

  const star = iconButton('important', todo.important ? '중요 표시 해제' : '중요 표시', todo.important ? '★' : '☆', 'star');
  star.setAttribute('aria-pressed', String(todo.important));
  star.disabled = readonly;
  li.append(star);

  const body = el('div', 'todo-body');
  if (editing) {
    const input = el('input', 'edit-input');
    input.type = 'text';
    input.maxLength = 100;
    input.value = draft;
    input.setAttribute('aria-label', '할 일 수정');
    body.append(input);
  } else {
    body.append(el('span', 'todo-text', todo.text));
    if (todo.tag) body.append(el('span', `tag tag-${todo.tag}`, TAG_LABELS[todo.tag]));
  }
  li.append(body);

  if (!readonly && !editing) {
    li.append(iconButton('edit', '수정', '✎'), iconButton('delete', '삭제', '✕', 'danger'));
  }
  return li;
}

export function render(state, els, ui) {
  const isToday = state.viewDate === state.today;
  const dayTodos = todosForDate(state.todos, state.viewDate);
  const { done, total } = progress(dayTodos);

  // 헤더
  els.date.textContent = formatKorean(state.viewDate);
  els.nextDay.disabled = isToday;
  els.goToday.hidden = isToday;
  els.title.textContent = isToday ? '오늘의 할일' : '지난 할일';

  const percent = total ? Math.round((done / total) * 100) : 0;
  els.progressText.textContent = `${done} / ${total} 완료`;
  els.progressFill.style.width = `${percent}%`;
  els.progressBar.setAttribute('aria-valuenow', String(percent));
  const allDone = total > 0 && done === total;
  els.celebrate.hidden = !allDone;
  els.celebrate.textContent = isToday ? '오늘 할 일을 모두 끝냈어요! 🎉' : '이 날 할 일을 모두 끝냈어요 🎉';

  const effectiveDark =
    state.settings.theme === 'dark' || (state.settings.theme === 'system' && ui.systemDark);
  els.themeToggle.textContent = effectiveDark ? '☀' : '☾';
  els.themeToggle.setAttribute('aria-label', effectiveDark ? '라이트 모드로 전환' : '다크 모드로 전환');
  els.themeToggle.title = els.themeToggle.getAttribute('aria-label');

  // 알림
  els.storageNotice.hidden = !ui.notice;
  els.storageNotice.textContent = ui.notice || '';

  const offer = isToday && shouldOfferCarryOver(state);
  els.carryBanner.hidden = !offer;
  if (offer) {
    const count = carryOverCandidates(state.todos, state.today, state.settings.lastVisitDate).length;
    els.carryText.textContent = `지난번에 못한 일 ${count}개를 오늘로 가져올까요?`;
  }

  // 입력
  els.composer.hidden = !isToday;
  els.readonlyNote.hidden = isToday;

  // 필터
  els.filterButtons.forEach((button) => {
    const active = button.dataset.filter === state.filter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });

  // 목록
  const visible = filterTodos(sortTodos(dayTodos), state.filter);
  const draggable = isToday && state.filter === 'all' && visible.length > 1;
  els.list.replaceChildren(
    ...visible.map((todo) =>
      renderItem(todo, {
        readonly: !isToday,
        draggable,
        editing: ui.editingId === todo.id,
        draft: ui.draft,
      }),
    ),
  );
  els.empty.hidden = visible.length > 0;
  els.empty.textContent = !isToday && total === 0 ? '이 날은 기록된 할 일이 없어요' : EMPTY_MESSAGES[state.filter];

  // 푸터
  els.remaining.textContent = `남은 할 일 ${total - done}개`;
  els.clearDone.hidden = !isToday;
  els.clearDone.disabled = done === 0;

  // 토스트
  const removed = state.lastRemoved;
  els.toast.classList.toggle('show', Boolean(removed));
  els.undoButton.tabIndex = removed ? 0 : -1;
  if (removed) {
    els.toastText.textContent =
      removed.length === 1 ? '할 일을 삭제했어요' : `완료된 항목 ${removed.length}개를 지웠어요`;
  }
}
