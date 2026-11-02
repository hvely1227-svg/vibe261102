import { test } from 'node:test';
import assert from 'node:assert/strict';
import { addDays, formatKorean, isValidKey } from '../js/date.js';
import { carryOverCandidates, normalizeText, reducer, sanitizeTodos, shouldOfferCarryOver, sortTodos } from '../js/todo.js';

const TODAY = '2026-11-02';
const YESTERDAY = '2026-11-01';

function makeState(overrides = {}) {
  return {
    todos: [],
    settings: { theme: 'system', lastVisitDate: TODAY },
    today: TODAY,
    viewDate: TODAY,
    filter: 'all',
    lastRemoved: null,
    ...overrides,
  };
}

function todo(fields) {
  return { id: fields.text, done: false, important: false, tag: null, date: TODAY, order: 0, createdAt: 0, ...fields };
}

test('date helpers', () => {
  assert.equal(formatKorean(TODAY), '2026년 11월 2일 (월)');
  assert.equal(addDays('2026-03-01', -1), '2026-02-28');
  assert.equal(isValidKey('2026-02-30'), false);
  assert.equal(isValidKey(TODAY), true);
});

test('normalizeText trims, rejects blank, caps at 100 chars', () => {
  assert.equal(normalizeText('  a  '), 'a');
  assert.equal(normalizeText('   '), null);
  assert.equal(normalizeText('x'.repeat(150)).length, 100);
});

test('ADD appends with increasing order and ignores blank input', () => {
  let state = reducer(makeState(), { type: 'ADD', text: '첫째' });
  state = reducer(state, { type: 'ADD', text: '둘째', tag: 'morning' });
  assert.deepEqual(state.todos.map((t) => [t.text, t.order, t.tag]), [['첫째', 0, null], ['둘째', 1, 'morning']]);
  assert.equal(reducer(state, { type: 'ADD', text: '  ' }), state);
});

test('TOGGLE sets and clears completedAt', () => {
  let state = makeState({ todos: [todo({ text: 'a' })] });
  state = reducer(state, { type: 'TOGGLE', id: 'a' });
  assert.equal(state.todos[0].done, true);
  assert.ok(state.todos[0].completedAt);
  state = reducer(state, { type: 'TOGGLE', id: 'a' });
  assert.equal(state.todos[0].done, false);
  assert.equal('completedAt' in state.todos[0], false);
});

test('past-day items are read-only', () => {
  const state = makeState({ todos: [todo({ text: 'old', date: YESTERDAY })] });
  for (const type of ['TOGGLE', 'TOGGLE_IMPORTANT', 'DELETE']) {
    assert.equal(reducer(state, { type, id: 'old' }), state);
  }
  assert.equal(reducer(state, { type: 'EDIT', id: 'old', text: 'new' }), state);
});

test('DELETE and CLEAR_DONE can be undone', () => {
  const base = makeState({ todos: [todo({ text: 'a' }), todo({ text: 'b', done: true }), todo({ text: 'c', done: true })] });
  let state = reducer(base, { type: 'DELETE', id: 'a' });
  assert.equal(state.todos.length, 2);
  state = reducer(state, { type: 'UNDO_REMOVE' });
  assert.equal(state.todos.length, 3);

  state = reducer(base, { type: 'CLEAR_DONE' });
  assert.deepEqual(state.todos.map((t) => t.id), ['a']);
  assert.equal(state.lastRemoved.length, 2);
  state = reducer(state, { type: 'UNDO_REMOVE' });
  assert.equal(state.todos.length, 3);
  assert.equal(state.lastRemoved, null);
});

test('sortTodos: important first, then active, then order', () => {
  const sorted = sortTodos([
    todo({ text: 'done', done: true, order: 0 }),
    todo({ text: 'b', order: 2 }),
    todo({ text: 'a', order: 1 }),
    todo({ text: 'star', important: true, order: 3 }),
  ]);
  assert.deepEqual(sorted.map((t) => t.text), ['star', 'a', 'b', 'done']);
});

test('carry-over offers unfinished items since last decision only', () => {
  const todos = [
    todo({ text: 'ignored-before', date: '2026-10-30' }),
    todo({ text: 'yesterday', date: YESTERDAY }),
    todo({ text: 'yesterday-done', date: YESTERDAY, done: true }),
  ];
  const settings = { theme: 'system', lastVisitDate: YESTERDAY };
  assert.deepEqual(carryOverCandidates(todos, TODAY, YESTERDAY).map((t) => t.text), ['yesterday']);

  let state = makeState({ todos, settings });
  assert.equal(shouldOfferCarryOver(state), true);
  state = reducer(state, { type: 'CARRY_OVER' });
  assert.equal(state.todos.find((t) => t.id === 'yesterday').date, TODAY);
  assert.equal(state.todos.find((t) => t.id === 'ignored-before').date, '2026-10-30');
  assert.equal(shouldOfferCarryOver(state), false);

  const dismissed = reducer(makeState({ todos, settings }), { type: 'DISMISS_CARRY_OVER' });
  assert.equal(shouldOfferCarryOver(dismissed), false);
  assert.equal(dismissed.todos.find((t) => t.id === 'yesterday').date, YESTERDAY);
});

test('SET_TODAY follows the new day only when viewing today', () => {
  const state = reducer(makeState(), { type: 'SET_TODAY', today: '2026-11-03' });
  assert.equal(state.viewDate, '2026-11-03');
  const past = reducer(makeState({ viewDate: YESTERDAY }), { type: 'SET_TODAY', today: '2026-11-03' });
  assert.equal(past.viewDate, YESTERDAY);
});

test('SET_VIEW_DATE cannot go into the future', () => {
  const state = makeState();
  assert.equal(reducer(state, { type: 'SET_VIEW_DATE', date: '2026-11-03' }), state);
  assert.equal(reducer(state, { type: 'SET_VIEW_DATE', date: YESTERDAY }).viewDate, YESTERDAY);
});

test('sanitizeTodos drops invalid entries and dedupes ids', () => {
  const result = sanitizeTodos([
    { id: 'x', text: 'ok', date: TODAY },
    { id: 'x', text: 'dup id', date: TODAY },
    { text: '', date: TODAY },
    { text: 'bad date', date: 'yesterday' },
    null,
  ]);
  assert.equal(result.length, 2);
  assert.notEqual(result[0].id, result[1].id);
  assert.equal(sanitizeTodos({}), null);
});
