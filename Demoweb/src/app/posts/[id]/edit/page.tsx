import { notFound } from "next/navigation";
import { Suspense } from "react";
import { updatePostAction } from "@/app/actions";
import { getPost } from "@/lib/posts";
import { PostForm } from "@/components/board/post-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function EditPostPage({ params }: PageProps<"/posts/[id]/edit">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글 수정</CardTitle>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <EditForm params={params} />
        </Suspense>
      </CardContent>
    </Card>
  );
}

async function EditForm({ params }: Pick<PageProps<"/posts/[id]/edit">, "params">) {
  const { id } = await params;
  const post = await getPost(Number(id));
  if (!post) notFound();

  return (
    <PostForm
      action={updatePostAction.bind(null, post.id)}
      defaultValues={{ title: post.title, author: post.author, content: post.content }}
      submitLabel="수정 완료"
      cancelHref={`/posts/${post.id}`}
    />
  );
}
