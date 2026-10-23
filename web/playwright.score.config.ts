import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,timeout:90000,testMatch:'score-position-management.spec.ts',use:{...base.use,baseURL:'http://localhost:3107'},webServer:{command:'npm run dev -- --port 3107',url:'http://localhost:3107',reuseExistingServer:true,timeout:120000}});
