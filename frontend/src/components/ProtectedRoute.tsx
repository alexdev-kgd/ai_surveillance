import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@context/AuthContext";

export const ProtectedRoute = ({ children }: { children: ReactNode }) => {
	const { user, authLoading } = useAuth();

	if (authLoading) return <div>Загрузка</div>;

	if (!user) return <Navigate to="/auth" replace />;

	return <>{children}</>;
};
