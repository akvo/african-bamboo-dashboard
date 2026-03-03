import { verifySession } from "@/lib/dal";
import { AuthProvider } from "@/context/AuthContext";
import { FormsProvider } from "@/hooks/useForms";
import { MapStateProvider } from "@/hooks/useMapState";
import { ExportProviderWithToast } from "@/components/export-toast";
import { AppSidebar } from "@/components/app-sidebar";

export const metadata = {
  title: "Dashboard - African Bamboo",
  description: "African Bamboo Carbon Sequestration Dashboard",
};

export default async function DashboardLayout({ children }) {
  const { user, token } = await verifySession();

  return (
    <AuthProvider user={user} token={token}>
      <FormsProvider>
        <MapStateProvider>
          <ExportProviderWithToast>
            <div className="flex h-screen">
              <AppSidebar />
              <main className="flex-1 overflow-auto bg-background p-6">
                {children}
              </main>
            </div>
          </ExportProviderWithToast>
        </MapStateProvider>
      </FormsProvider>
    </AuthProvider>
  );
}
