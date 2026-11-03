import "server-only";

import { neon } from "@neondatabase/serverless";
import { connection } from "next/server";

export type Post = {
  id: number;
  title: string;
  author: string;
  content: string;
  createdAt: string;
  updatedAt: string;
};

export type PostInput = Pick<Post, "title" | "author" | "content">;

type PostRow = {
  id: number;
  title: string;
  author: string;
  content: string;
  created_at: Date;
  updated_at: Date;
};

function getSql() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env.local 파일을 확인하세요.");
  return neon(url);
}

// 서버 프로세스당 한 번만 테이블을 준비
let schemaReady: Promise<void> | undefined;
function ensureSchema() {
  schemaReady ??= (async () => {
    const sql = getSql();
    await sql`
      CREATE TABLE IF NOT EXISTS posts (
        id SERIAL PRIMARY KEY,
        title VARCHAR(100) NOT NULL,
        author VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `;
  })().catch((err) => {
    schemaReady = undefined;
    throw err;
  });
  return schemaReady;
}

async function query(): Promise<ReturnType<typeof getSql>> {
  await ensureSchema();
  return getSql();
}

function toPost(row: PostRow): Post {
  return {
    id: row.id,
    title: row.title,
    author: row.author,
    content: row.content,
    createdAt: new Date(row.created_at).toISOString(),
    updatedAt: new Date(row.updated_at).toISOString(),
  };
}

export async function listPosts(): Promise<Post[]> {
  // 요청마다 최신 데이터를 읽도록 동적 렌더링으로 지정
  await connection();
  const sql = await query();
  const rows = (await sql`SELECT * FROM posts ORDER BY id DESC`) as PostRow[];
  return rows.map(toPost);
}

export async function getPost(id: number): Promise<Post | undefined> {
  await connection();
  if (!Number.isInteger(id)) return undefined;
  const sql = await query();
  const rows = (await sql`SELECT * FROM posts WHERE id = ${id}`) as PostRow[];
  return rows[0] && toPost(rows[0]);
}

export async function createPost(input: PostInput): Promise<Post> {
  const sql = await query();
  const rows = (await sql`
    INSERT INTO posts (title, author, content)
    VALUES (${input.title}, ${input.author}, ${input.content})
    RETURNING *
  `) as PostRow[];
  return toPost(rows[0]);
}

export async function updatePost(id: number, input: PostInput): Promise<Post | undefined> {
  const sql = await query();
  const rows = (await sql`
    UPDATE posts
    SET title = ${input.title}, author = ${input.author}, content = ${input.content}, updated_at = now()
    WHERE id = ${id}
    RETURNING *
  `) as PostRow[];
  return rows[0] && toPost(rows[0]);
}

export async function deletePost(id: number): Promise<boolean> {
  const sql = await query();
  const rows = await sql`DELETE FROM posts WHERE id = ${id} RETURNING id`;
  return rows.length > 0;
}
