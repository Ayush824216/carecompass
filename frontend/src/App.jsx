import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppProvider } from "./context/AppContext.jsx";
import Layout from "./components/Layout.jsx";
import Home from "./pages/Home.jsx";
import GetCare from "./pages/GetCare.jsx";
import Caregivers from "./pages/Caregivers.jsx";
import HowItWorks from "./pages/HowItWorks.jsx";
import Developers from "./pages/Developers.jsx";
import Bookings from "./pages/Bookings.jsx";
import NotFound from "./pages/NotFound.jsx";
import Memory from "./pages/Memory.jsx";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="care" element={<GetCare />} />
            <Route path="caregivers" element={<Caregivers />} />
            <Route path="how-it-works" element={<HowItWorks />} />
            <Route path="developers" element={<Developers />} />
            <Route path="bookings" element={<Bookings />} />
            <Route path="memory" element={<Memory />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
