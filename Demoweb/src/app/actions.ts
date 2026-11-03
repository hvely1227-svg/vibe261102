"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import * as posts from "@/lib/posts";

export type PostFormState = {
  errors?: Partial<Record<keyof posts.PostInput, string>>;
  message?: string;
  values?: posts.PostInput;
};

function parseForm(formData: FormData) {
  const values: posts.PostInput = {
    title: String(formData.get("title") ?? "").trim(),
    author: String(formData.get("author") ?? "").trim(),
    content: String(formData.get("content") ?? "").replace(/\r\n/g, "\n").trim(),
  };
  const errors: PostFormState["errors"] = {};
  if (!values.title) errors.title = "제목을 입력해 주세요.";
  else if (values.title.length > 100) errors.title = "제목은 100자 이내로 입력해 주세요.";
  if (!values.author) errors.author = "작성자를 입력해 주세요.";
  else if (values.author.length > 20) errors.author = "작성자는 20자 이내로 입력해 주세요.";
  if (!values.content) errors.content = "내용을 입력해 주세요.";
  else if (values.content.length > 5000) errors.content = "내용은 5000자 이내로 입력해 주세요.";
  return { values, errors };
}

export async function createPostAction(
  _prev: PostFormState,
  formData: FormData,
): Promise<PostFormState> {
  const { values, errors } = parseForm(formData);
  if (Object.keys(errors).length > 0) return { errors, values };

  const post = await posts.createPost(values);
  revalidatePath("/");
  redirect(`/posts/${post.id}`);
}

export async function updatePostAction(
  id: number,
  _prev: PostFormState,
  formData: FormData,
): Promise<PostFormState> {
  const { values, errors } = parseForm(formData);
  if (Object.keys(errors).length > 0) return { errors, values };

  const post = await posts.updatePost(id, values);
  if (!post) return { message: "글을 찾을 수 없습니다. 이미 삭제되었을 수 있습니다.", values };
  revalidatePath("/");
  redirect(`/posts/${id}`);
}

export async function deletePostAction(id: number) {
  await posts.deletePost(id);
  revalidatePath("/");
  redirect("/");
}
