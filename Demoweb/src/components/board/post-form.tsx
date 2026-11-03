"use client";

import Link from "next/link";
import { useActionState } from "react";
import type { PostFormState } from "@/app/actions";
import type { PostInput } from "@/lib/posts";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  action: (state: PostFormState, formData: FormData) => Promise<PostFormState>;
  defaultValues?: PostInput;
  submitLabel: string;
  cancelHref: string;
};

export function PostForm({ action, defaultValues, submitLabel, cancelHref }: Props) {
  const [state, formAction, pending] = useActionState(action, {});
  const values = state.values ?? defaultValues;

  return (
    <form action={formAction} className="flex flex-col gap-5" noValidate>
      {state.message && (
        <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {state.message}
        </p>
      )}

      <Field label="제목" name="title" error={state.errors?.title}>
        <Input
          id="title"
          name="title"
          placeholder="제목을 입력하세요"
          defaultValue={values?.title}
          maxLength={100}
          aria-invalid={!!state.errors?.title}
        />
      </Field>

      <Field label="작성자" name="author" error={state.errors?.author}>
        <Input
          id="author"
          name="author"
          placeholder="이름 또는 닉네임"
          defaultValue={values?.author}
          maxLength={20}
          className="sm:max-w-xs"
          aria-invalid={!!state.errors?.author}
        />
      </Field>

      <Field label="내용" name="content" error={state.errors?.content}>
        <Textarea
          id="content"
          name="content"
          placeholder="내용을 입력하세요"
          defaultValue={values?.content}
          rows={12}
          maxLength={5000}
          className="min-h-64"
          aria-invalid={!!state.errors?.content}
        />
      </Field>

      <div className="flex justify-end gap-2">
        <Link href={cancelHref} className={buttonVariants({ variant: "outline", size: "lg" })}>
          취소
        </Link>
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? "저장 중..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  name,
  error,
  children,
}: {
  label: string;
  name: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={name}>{label}</Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
