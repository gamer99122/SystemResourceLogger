using System.Diagnostics;
using System.Text;

namespace SystemResourceLogger;

class Program
{
    // User mentioned 64GB, but let's try to detect it or just report available/used.
    // GC.GetGCMemoryInfo().TotalAvailableMemoryBytes is available in .NET 8.
    static long _totalPhysicalMemoryBytes;

    static async Task Main(string[] args)
    {
        Console.WriteLine("System Resource Logger Started.");
        Console.WriteLine($"Press Ctrl+C to stop.");
        
        // Try to get total physical memory.
        var gcMemoryInfo = GC.GetGCMemoryInfo();
        _totalPhysicalMemoryBytes = gcMemoryInfo.TotalAvailableMemoryBytes;
        
        Console.WriteLine($"Detected Total Memory: {_totalPhysicalMemoryBytes / 1024 / 1024} MB");
        Console.WriteLine("Logging every 5 minutes...");

        // Ensure we handle encoding correctly for CSV (UTF-8 usually best).
        // If opening in Excel directly in traditional regions, sometimes BOM is needed.
        
        while (true)
        {
            try
            {
                await LogSystemStatus();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error logging status: {ex.Message}");
            }

            // Wait 5 minutes
            await Task.Delay(TimeSpan.FromMinutes(5));
        }
    }

    static async Task LogSystemStatus()
    {
        var now = DateTime.Now;
        var fileName = $"{now:yyyy-MM-dd}_log.csv";
        var filePath = Path.Combine(@"D:\C\Desk\Code\Tool\SystemResourceLogger", fileName);
        
        bool fileExists = File.Exists(filePath);

        // Get Memory Info
        // Option 1: PerformanceCounter (Windows specific)
        // Option 2: GC.GetGCMemoryInfo (Simpler, Cross-platform-ish)
        // Let's use GC info for total, but for "Available", PerformanceCounter is standard on Windows.
        
        float availableMb = 0;
        float poolNonPagedMb = 0;
        float poolPagedMb = 0;
        
        if (OperatingSystem.IsWindows())
        {
            try
            {
                using (var pcAvail = new PerformanceCounter("Memory", "Available MBytes"))
                using (var pcNonPaged = new PerformanceCounter("Memory", "Pool Nonpaged Bytes"))
                using (var pcPaged = new PerformanceCounter("Memory", "Pool Paged Bytes"))
                {
                    availableMb = pcAvail.NextValue();
                    poolNonPagedMb = pcNonPaged.NextValue() / 1024 / 1024;
                    poolPagedMb = pcPaged.NextValue() / 1024 / 1024;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error reading perf counters: {ex.Message}");
            }
        }

        long totalMb = _totalPhysicalMemoryBytes / 1024 / 1024;
        float usedMb = totalMb - availableMb;
        float usagePercent = (usedMb / totalMb) * 100;

        // Get Top 10 Processes by Memory
        var processes = Process.GetProcesses();
        
        var topMemProcesses = processes
            .OrderByDescending(p => p.WorkingSet64)
            .Take(10)
            .Select(p => new { Name = p.ProcessName, Value = p.WorkingSet64 / 1024 / 1024 }) // MB
            .ToList();

        // Get Top 5 Processes by Handle Count (Leak Detection)
        var topHandleProcesses = processes
            .OrderByDescending(p => p.HandleCount)
            .Take(5)
            .Select(p => new { Name = p.ProcessName, Value = (long)p.HandleCount })
            .ToList();

        // Build CSV Line
        var sb = new StringBuilder();
        
        // Header
        if (!fileExists)
        {
            sb.Append("Timestamp,TotalMB,AvailableMB,UsedMB,Usage%,NonPagedPoolMB,PagedPoolMB,");
            for (int i = 1; i <= 10; i++) sb.Append($"TopMem{i}_Name,TopMem{i}_MB,");
            for (int i = 1; i <= 5; i++) sb.Append($"TopHandle{i}_Name,TopHandle{i}_Count,");
            sb.AppendLine();
        }

        sb.Append($"{now:yyyy-MM-dd HH:mm:ss},{totalMb},{availableMb},{usedMb},{usagePercent:F2},{poolNonPagedMb:F2},{poolPagedMb:F2},");
        
        // Memory Top 10
        foreach (var p in topMemProcesses)
        {
            sb.Append($"{p.Name},{p.Value},");
        }
        for (int i = topMemProcesses.Count; i < 10; i++) sb.Append(",,");
        
        // Handle Top 5
        foreach (var p in topHandleProcesses)
        {
            sb.Append($"{p.Name},{p.Value},");
        }
        for (int i = topHandleProcesses.Count; i < 5; i++) sb.Append(",,");

        sb.AppendLine();

        // Append to file
        await File.AppendAllTextAsync(filePath, sb.ToString(), Encoding.UTF8);
        
        Console.WriteLine($"Logged at {now:HH:mm:ss}: Used {usedMb} MB ({usagePercent:F2}%) | NonPaged: {poolNonPagedMb:F2} MB");
    }
}