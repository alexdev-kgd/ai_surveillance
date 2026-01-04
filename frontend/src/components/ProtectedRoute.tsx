import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { hasToken } from "../services/auth.service";

export const ProtectedRoute = ({ children }: { children: ReactNode }) => {
	if (!hasToken()) return <Navigate to="/auth" replace />;

	return <>{children}</>;
};
