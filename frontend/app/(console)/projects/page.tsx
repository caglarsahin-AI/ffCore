"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ProjectForm } from "@/components/project-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WriteGate } from "@/components/write-gate";
import { useProjects } from "@/lib/api/queries";

export default function ProjectsPage() {
  const t = useTranslations("Projects");
  const { isSuperadmin } = useAccess();
  const projects = useProjects();
  const [creating, setCreating] = useState(false);

  // Creating a project is a tenant action (03a: superadmin only); other admins do not get the button.
  const action = isSuperadmin ? (
    <WriteGate>
      <Button onClick={() => setCreating(true)} disabled={creating} data-testid="primary-action">
        <PlusIcon />
        {t("create")}
      </Button>
    </WriteGate>
  ) : null;

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {creating && <ProjectForm onDone={() => setCreating(false)} />}
      <ListState query={projects} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="projects-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("descriptionLabel")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("members")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((project) => (
                <TableRow key={project.id} data-testid={`project-${project.key}`}>
                  <TableCell className="font-mono">{project.key}</TableCell>
                  <TableCell>{project.name}</TableCell>
                  <TableCell className="text-muted-foreground">{project.description}</TableCell>
                  <TableCell className="text-right">
                    <Link className="text-primary underline-offset-4 hover:underline" href={`/projects/${project.id}/members`}>
                      {t("members")}
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
