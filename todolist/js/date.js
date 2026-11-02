// 날짜 유틸: 모든 날짜는 사용자 로컬 시간대 기준 "YYYY-MM-DD" 키로 다룬다.

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function toKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function todayKey(now = new Date()) {
  return toKey(now);
}

export function fromKey(key) {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(key, days) {
  const date = fromKey(key);
  date.setDate(date.getDate() + days);
  return toKey(date);
}

export function isValidKey(key) {
  if (typeof key !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(key)) return false;
  return toKey(fromKey(key)) === key;
}

// "2026년 11월 2일 (월)"
export function formatKorean(key) {
  const date = fromKey(key);
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAYS[date.getDay()]})`;
}
