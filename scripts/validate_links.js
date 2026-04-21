const fs = require('fs');
const path = require('path');

// Config
const APPS_DIR = path.join(__dirname, '../websites/apps');
const APPS = ['marketing', 'docs', 'support', 'payments'];

// Helper to recursively find files
function findFiles(dir, extension, fileList = []) {
  const files = fs.readdirSync(dir);
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      if (file !== 'node_modules' && file !== '.next') {
        findFiles(filePath, extension, fileList);
      }
    } else {
      if (filePath.endsWith(extension) || filePath.endsWith('.ts')) {
        fileList.push(filePath);
      }
    }
  });
  return fileList;
}

// Helper to find page file for a route
function routeExists(appPath, route) {
  // Handle root
  if (route === '/') return fs.existsSync(path.join(appPath, 'src/app/page.tsx'));

  // Strip query params/hashes
  const cleanRoute = route.split('?')[0].split('#')[0];
  const parts = cleanRoute.split('/').filter(Boolean);
  
  // Construct path candidates
  // 1. /path/page.tsx
  const candidate1 = path.join(appPath, 'src/app', ...parts, 'page.tsx');
  if (fs.existsSync(candidate1)) return true;

  // 2. /path/route.ts (API)
  const candidate2 = path.join(appPath, 'src/app', ...parts, 'route.ts');
  if (fs.existsSync(candidate2)) return true;

  // 3. Dynamic routes (simplified check - assumes [param] folder exists)
  let currentDir = path.join(appPath, 'src/app');
  for (const part of parts) {
    const direct = path.join(currentDir, part);
    if (fs.existsSync(direct) && fs.statSync(direct).isDirectory()) {
      currentDir = direct;
      continue;
    }
    
    // Check for [param] folders
    if (!fs.existsSync(currentDir)) return false;
    
    const subdirs = fs.readdirSync(currentDir).filter(d => {
      try {
        return fs.statSync(path.join(currentDir, d)).isDirectory();
      } catch (e) { return false; }
    });
    
    const dynamicDir = subdirs.find(d => d.startsWith('[') && d.endsWith(']'));
    if (dynamicDir) {
      currentDir = path.join(currentDir, dynamicDir);
      continue;
    }
    
    return false; // Path segment not found
  }
  
  // If we walked the whole path, check for page.tsx
  return fs.existsSync(path.join(currentDir, 'page.tsx'));
}

async function scan() {
  let hasErrors = false;

  for (const app of APPS) {
    console.log(`\nScanning ${app}...`);
    const appDir = path.join(APPS_DIR, app);
    
    if (!fs.existsSync(appDir)) {
        console.log(`  Skipping ${app} (directory not found)`);
        continue;
    }

    const files = findFiles(path.join(appDir, 'src/app'), '.tsx');

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      
      // Match href="..." and href={'...'}
      const regex = /href=['"]([^'"]+)['"]|href={['"]([^'"]+)['"]}/g;
      let match;
      
      while ((match = regex.exec(content)) !== null) {
        const url = match[1] || match[2];
        
        if (!url) continue;
        if (url.startsWith('http')) continue; // Skip external
        if (url.startsWith('mailto:')) continue;
        if (url.startsWith('#')) continue; // Skip anchors
        
        // Handle cross-app links (e.g. docs.runprep.io/...)
        if (url.includes('runprep.io')) continue;

        // Internal links
        if (url.startsWith('/')) {
          if (!routeExists(appDir, url)) {
            console.error(`  ❌ Broken link in ${path.relative(appDir, file)}: ${url}`);
            hasErrors = true;
          }
        }
      }
    }
  }

  if (hasErrors) {
    console.error('\nFound broken links!');
    process.exit(1);
  } else {
    console.log('\n✅ All internal links validated.');
  }
}

scan();
