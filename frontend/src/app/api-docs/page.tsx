"use client";


import dynamic from "next/dynamic";
const Redoc = dynamic(() => import("redoc").then(m => m.RedocStandalone), { ssr: false });
export default function ApiDocsPage() { return <Redoc specUrl="/openapi.json" />; }


// // src/app/api-docs/page.tsx
// export default function ApiDocsPage() {
//   return (
//     <iframe
//       src="/api-docs.html"            // copy api-docs.html to /public or serve from pydoc
//       style={{ width: "100%", height: "100vh", border: "none" }}
//       title="API docs"
//     />
//   );
// }
