import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import BookingsPage from "./pages/BookingsPage";
import ExplorePage from "./pages/ExplorePage";
import NotFoundPage from "./pages/NotFoundPage";
import PlanTripPage from "./pages/PlanTripPage";
import TripPage from "./pages/TripPage";
import TripsPage from "./pages/TripsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PlanTripPage />} />
        <Route path="trips" element={<TripsPage />} />
        <Route path="trips/:tripId" element={<TripPage />} />
        <Route path="explore" element={<ExplorePage />} />
        <Route path="bookings" element={<BookingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
