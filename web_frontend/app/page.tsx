import { UploadForm } from "@/components/UploadForm"

export default function Home() {
  return (
    <main className="min-h-screen bg-muted/30 p-6 md:p-12">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="flex flex-col gap-2 border-b pb-6">
          <h1 className="text-3xl font-bold tracking-tight text-primary">WeldWarp</h1>
          <p className="text-muted-foreground">ILI Pipeline Alignment & Corrosion Growth Prediction System</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Controls */}
          <div className="lg:col-span-1 space-y-6">
            <section>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                Start New Analysis
              </h2>
              <UploadForm />
            </section>

            {/* Placeholder for Job List */}
            <section className="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
              <h3 className="font-semibold mb-3">Recent Activity</h3>
              <div className="text-sm text-muted-foreground py-4 text-center border rounded-md border-dashed">
                No recent jobs found.
              </div>
            </section>
          </div>

          {/* Right Column: Results / Visualization */}
          <div className="lg:col-span-2 space-y-6">
            <section className="rounded-xl border bg-card text-card-foreground shadow-sm h-full min-h-[500px] p-8 flex flex-col items-center justify-center text-center">
              <div className="bg-muted/50 p-6 rounded-full mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" /><path d="M3 5v14a2 2 0 0 0 2 2h16v-5" /><path d="M18 12a2 2 0 0 0 0 4h4v-4Z" /></svg>
              </div>
              <div className="max-w-md space-y-2">
                <h3 className="text-xl font-semibold">Waiting for Data</h3>
                <p className="text-muted-foreground">
                  Upload your run data on the left to begin the matching and alignment process. Results will appear here.
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
