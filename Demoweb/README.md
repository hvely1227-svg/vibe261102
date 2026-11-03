# DemoWeb 게시판

Next.js(App Router) + TypeScript + shadcn/ui(Tailwind CSS v4)로 만든 간단한 게시판입니다.

## 기능

- 글 목록 (`/`, 10개 단위 페이지 이동)
- 글 상세 (`/posts/[id]`)
- 글쓰기 (`/posts/new`), 수정 (`/posts/[id]/edit`), 삭제 (상세 페이지의 확인 대화상자)

글 데이터는 [Neon](https://neon.tech) PostgreSQL의 `posts` 테이블에 저장되며, 테이블이 없으면 첫 요청 때 자동으로 만들어집니다.

## 실행

`.env.example`을 `.env.local`로 복사하고 `DATABASE_URL`에 Neon 연결 문자열을 넣습니다. (`.env.local`은 git에 포함되지 않습니다.)

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # 프로덕션 빌드
npm start       # 빌드 결과 실행
```

## 구조

- `src/lib/posts.ts` — Neon PostgreSQL 저장소 (`@neondatabase/serverless`)
- `src/app/actions.ts` — 글 생성·수정·삭제 Server Actions (입력값 검증 포함)
- `src/app/**/page.tsx` — 목록·상세·글쓰기·수정 페이지
- `src/components/board/` — 글 작성 폼, 삭제 버튼
- `src/components/ui/` — shadcn/ui 컴포넌트
