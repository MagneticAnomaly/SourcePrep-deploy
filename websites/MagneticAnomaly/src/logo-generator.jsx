import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import FaviconScene from './FaviconScene.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <FaviconScene />
  </StrictMode>,
);
