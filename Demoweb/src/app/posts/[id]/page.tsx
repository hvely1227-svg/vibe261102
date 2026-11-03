import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft, Pencil } from "lucide-react";
import { getPost } from "@/lib/posts";
import { formatDateTime } from "@/lib/format";
import { DeletePostButton } from "@/components/board/delete-post-button";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
      <PostDetail params={params} />
    </Suspense>
  );
}

async function PostDetail({ params }: Pick<PageProps<"/posts/[id]">, "params">) {
  const { id } = await params;
  const post = await getPost(Number(id));
  if (!post) notFound();

  const edited = post.updatedAt !== post.createdAt;

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-2xl leading-snug break-words">{post.title}</CardTitle>
        <CardDescription className="flex flex-wrap gap-x-3 gap-y-1">
          <span>{post.author}</span>
          <span>{formatDateTime(post.createdAt)}</span>
          {edited && <span>(수정됨 {formatDateTime(post.updatedAt)})</span>}
        </CardDescription>
      </CardHeader>
      <CardContent className="min-h-48 py-2 leading-relaxed break-words whitespace-pre-wrap">
        {post.content}
      </CardContent>
      <CardFooter className="justify-between gap-2 border-t">
        <Link href="/" className={buttonVariants({ variant: "outline", size: "lg" })}>
          <ArrowLeft />
          목록
        </Link>
        <div className="flex gap-2">
          <Link href={`/posts/${post.id}/edit`} className={buttonVariants({ variant: "secondary", size: "lg" })}>
            <Pencil />
            수정
          </Link>
          <DeletePostButton id={post.id} />
        </div>
      </CardFooter>
    </Card>
  );
}
