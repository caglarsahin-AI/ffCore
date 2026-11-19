"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from "@/components/ui/alert-dialog";

// The real retention pass deletes data and does not follow RETENTION_DRY_RUN (FOLLOWUP-130):
// the dialog says so before anything starts; cancel is the default focus.
export function RetentionRunConfirm({ open, onCancel, onConfirm }: { open: boolean; onCancel: () => void; onConfirm: () => void }) {
  const t = useTranslations("Retention.confirm");
  return (
    <AlertDialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <AlertDialogContent data-testid="retention-run-dialog">
        <AlertDialogTitle>{t("title")}</AlertDialogTitle>
        <AlertDialogDescription>{t("body")}</AlertDialogDescription>
        <p className="text-sm">{t("dryRunHint")}</p>
        <AlertDialogFooter>
          <Button variant="outline" onClick={onCancel} autoFocus data-testid="retention-run-cancel">
            {t("cancel")}
          </Button>
          <Button variant="destructive" onClick={onConfirm} data-testid="retention-run-confirm">
            {t("confirm")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
