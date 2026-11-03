import Link from "next/link";
import { Suspense } from "react";
import { listPosts } from "@/lib/posts";
import { formatDate } from "@/lib/format";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 10;

export default function HomePage({ searchParams }: PageProps<"/">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">전체 글</CardTitle>
        <CardDescription>자유롭게 글을 남겨 주세요.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <PostList searchParams={searchParams} />
        </Suspense>
      </CardContent>
    </Card>
  );
}

async function PostList({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const { page: pageParam } = await searchParams;
  const posts = await listPosts();

  if (posts.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
        <p>아직 작성된 글이 없습니다.</p>
        <Link href="/posts/new" className={buttonVariants({ variant: "outline" })}>
          첫 글 작성하기
        </Link>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(posts.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, Number(pageParam) || 1), totalPages);
  const items = posts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4">
      <table className="w-full table-fixed text-sm">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="hidden w-16 py-2 font-medium sm:table-cell">번호</th>
            <th className="py-2 text-left font-medium">제목</th>
            <th className="w-24 py-2 font-medium sm:w-28">작성자</th>
            <th className="hidden w-28 py-2 font-medium sm:table-cell">작성일</th>
          </tr>
        </thead>
        <tbody>
          {items.map((post) => (
            <tr key={post.id} className="border-b last:border-0 hover:bg-muted/50">
              <td className="hidden py-3 text-center text-muted-foreground sm:table-cell">{post.id}</td>
              <td className="py-3 pr-2">
                <Link href={`/posts/${post.id}`} className="block truncate hover:underline">
                  {post.title}
                </Link>
              </td>
              <td className="truncate py-3 text-center">{post.author}</td>
              <td className="hidden py-3 text-center text-muted-foreground sm:table-cell">
                {formatDate(post.createdAt)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {totalPages > 1 && (
        <nav aria-label="페이지" className="flex justify-center gap-1">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
            <Link
              key={n}
              href={n === 1 ? "/" : `/?page=${n}`}
              aria-current={n === page ? "page" : undefined}
              className={cn(buttonVariants({ variant: n === page ? "default" : "ghost", size: "icon" }))}
            >
              {n}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
