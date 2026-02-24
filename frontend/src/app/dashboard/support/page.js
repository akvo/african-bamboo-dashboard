import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { LifeBuoy, Mail, BookOpen, FolderCode, Smartphone } from "lucide-react";

const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL;

const resources = [
  {
    icon: BookOpen,
    title: "African Bamboo ODK External Validations Guide",
    description:
      "Learn how to set up external validations for your ODK forms with this step-by-step guide",
    href: "https://wiki.cloud.akvo.org/books/african-bamboo-odk-external-validations",
  },
  {
    icon: FolderCode,
    title: "African Bamboo GitHub Repository",
    description:
      "Explore the code, report issues, or contribute to the African Bamboo Dashboard on GitHub",
    href: "https://github.com/akvo/african-bamboo-dashboard",
  },
  {
    icon: Smartphone,
    title: "African Bamboo Mobile App",
    description:
      "Download the African Bamboo mobile app for Android to validate your ODK forms in the field",

    href: "https://github.com/akvo/african-bamboo-odk-external-validations/releases",
  },
];

export default function SupportPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Support</h1>
        <p className="text-sm text-muted-foreground">
          Get help with the African Bamboo Dashboard
        </p>
      </div>

      {/* Contact Support */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="size-5" />
            Contact Support
          </CardTitle>
          <CardDescription>
            Reach out to the team for help with technical issues, data
            questions, or feature requests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {supportEmail ? (
            <a
              href={`mailto:${supportEmail}`}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Mail className="size-4" />
              {supportEmail}
            </a>
          ) : (
            <p className="text-sm text-muted-foreground">
              No support email configured. Please contact your system
              administrator.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Helpful Resources */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LifeBuoy className="size-5" />
            Helpful Resources
          </CardTitle>
          <CardDescription>
            Explore guides, documentation, and tools to get the most out of the
            African Bamboo Dashboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {resources.map((resource) => (
            <a
              key={resource.href}
              href={resource.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-3 rounded-md border p-3 transition-colors hover:bg-muted"
            >
              <resource.icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">{resource.title}</p>
                <p className="text-xs text-muted-foreground">
                  {resource.description}
                </p>
              </div>
            </a>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
