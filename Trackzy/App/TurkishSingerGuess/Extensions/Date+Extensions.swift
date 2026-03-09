import Foundation

extension Date {
    
    /// Returns the start of the day in Turkish timezone
    var startOfDayInTurkey: Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Istanbul")!
        return calendar.startOfDay(for: self)
    }
    
    /// Returns a formatted date string (YYYY-MM-DD) in Turkish timezone
    var dateStringInTurkey: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Europe/Istanbul")
        return formatter.string(from: self)
    }
    
    /// Creates a date from a YYYY-MM-DD string
    static func from(dateString: String) -> Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Europe/Istanbul")
        return formatter.date(from: dateString)
    }
}

extension String {
    
    /// Converts a YYYY-MM-DD date string to a display-friendly format
    func toDisplayDate(style: DateFormatter.Style = .medium) -> String? {
        let inputFormatter = DateFormatter()
        inputFormatter.dateFormat = "yyyy-MM-dd"
        
        guard let date = inputFormatter.date(from: self) else {
            return nil
        }
        
        let outputFormatter = DateFormatter()
        outputFormatter.dateStyle = style
        outputFormatter.locale = Locale(identifier: "tr_TR")
        
        return outputFormatter.string(from: date)
    }
}
