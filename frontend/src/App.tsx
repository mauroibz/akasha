import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "@/pages/HomePage";
import { AddPage } from "@/pages/AddPage";
import { DetailPage } from "@/pages/DetailPage";
import { ImportPage } from "@/pages/ImportPage";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/add" element={<AddPage />} />
          <Route path="/books/:entryId" element={<DetailPage />} />
          <Route path="/import" element={<ImportPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
