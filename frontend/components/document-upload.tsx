"use client";

import { UploadIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import { CheckField, CheckGroup } from "@/components/form-parts";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { ASSIGNABLE_ROLES } from "@/lib/access";
import type { Role } from "@/lib/access";
import { useUploadDocuments } from "@/lib/api/knowledge-queries";
import type { UploadResult } from "@/lib/api/knowledge-queries";

type Assignable = (typeof ASSIGNABLE_ROLES)[number];

// Drag-and-drop or picked files, one request per upload with progress. Who may read is an explicit
// choice: roles (analyst pre-selected, the backend default made visible) or every member (acl_open).
// The upload result shows each file's outcome; the gates' decisions appear in the document list.
// In read mode the form is for viewing: every field is disabled, not only the button (brief 10,
// review r1 MINOR-2).
export function DocumentUpload({ projectId, kbId }: { projectId: string; kbId: string }) {
  const t = useTranslations("Documents");
  const tAccess = useTranslations("Access");
  const send = useUploadDocuments(projectId, kbId);
  const { canWrite } = useAccess(projectId);
  const report = useReportError();
  const input = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [roles, setRoles] = useState<Assignable[]>(["analyst"]);
  const [open, setOpen] = useState(false);
  const [aclError, setAclError] = useState<string>();
  const [progress, setProgress] = useState<number | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);

  function pick(list: FileList | null) {
    if (!canWrite) return;
    setFiles(list ? Array.from(list) : []);
    setResult(null);
  }

  async function onUpload() {
    if (!open && roles.length === 0) {
      setAclError(t("aclRequired"));
      return;
    }
    setAclError(undefined);
    setProgress(0);
    try {
      const uploaded = await send.mutateAsync({
        files,
        aclRoles: open ? [] : (roles as Role[]),
        aclOpen: open,
        onProgress: setProgress,
      });
      setResult(uploaded);
      setFiles([]);
      if (input.current) input.current.value = "";
    } catch (error) {
      report(error);
    } finally {
      setProgress(null);
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border bg-card p-6" aria-labelledby={`${inputId}-title`} data-testid="document-upload">
      <h2 id={`${inputId}-title`} className="text-lg font-medium">
        {t("uploadTitle")}
      </h2>
      <fieldset disabled={!canWrite} className="flex min-w-0 flex-col gap-4" data-testid="upload-fields">
        <div
          className={`flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-8 text-center ${
            dragging ? "border-primary bg-muted" : "border-input"
          }`}
          onDragOver={(event) => {
            event.preventDefault();
            if (canWrite) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            pick(event.dataTransfer.files);
          }}
          data-testid="drop-zone"
        >
          <UploadIcon className="size-6 text-muted-foreground" aria-hidden />
          <p className="max-w-md text-sm text-muted-foreground">{t("dropHint")}</p>
          <label htmlFor={inputId} className="cursor-pointer text-sm font-medium text-primary underline-offset-4 hover:underline">
            {t("choose")}
          </label>
          <input
            ref={input}
            id={inputId}
            type="file"
            multiple
            className="sr-only"
            onChange={(event) => pick(event.target.files)}
            data-testid="file-input"
          />
          {files.length > 0 && (
            <p className="text-sm" data-testid="selected-files">
              {t("selected", { count: files.length, names: files.map((file) => file.name).join(", ") })}
            </p>
          )}
        </div>
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-medium">{t("aclLegend")}</legend>
          <CheckGroup
            id="acl-roles"
            legend={t("aclRoles")}
            options={ASSIGNABLE_ROLES.map((role) => ({ value: role, label: tAccess(`roles.${role}`), disabled: open }))}
            selected={open ? [] : roles}
            onChange={setRoles}
            error={aclError}
          />
          <CheckField id="acl-open" label={t("aclOpen")} checked={open} onChange={setOpen} />
          <p className="text-sm text-muted-foreground">{t("aclOpenHint")}</p>
        </fieldset>
      </fieldset>
      {progress !== null && (
        <div className="flex flex-col gap-1" data-testid="upload-progress">
          <progress className="h-2 w-full accent-primary" value={progress} max={1} aria-label={t("uploading", { percent: Math.round(progress * 100) })} />
          <p className="text-sm text-muted-foreground">{t("uploading", { percent: Math.round(progress * 100) })}</p>
        </div>
      )}
      <div>
        <WriteGate projectId={projectId}>
          <Button onClick={onUpload} disabled={files.length === 0 || send.isPending} data-testid="upload-button">
            {t("upload")}
          </Button>
        </WriteGate>
      </div>
      {result && (
        <div className="flex flex-col gap-1" data-testid="upload-result">
          <h3 className="text-sm font-medium">{t("outcomesTitle")}</h3>
          <ul className="text-sm">
            {result.data.map(({ outcome, document }) => (
              <li key={document.id} data-outcome={outcome}>
                {t("outcomeLine", { file: document.filename, outcome: t(`outcomes.${outcome}`) })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
