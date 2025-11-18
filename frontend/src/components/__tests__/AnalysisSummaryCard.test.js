import React from "react";
import { render, screen } from "@testing-library/react";
import AnalysisSummaryCard from "../AnalysisSummaryCard";
import { createAnalysisEntry } from "../../utils/analysisUtils";

const buildSampleResponse = () => ({
  engine: "ChatGPT",
  engine_key: "chatgpt",
  message: "1 dosya ChatGPT ile analiz edildi.",
  summaries: [
    {
      filename: "test-report.pdf",
      total_tests: 10,
      passed_tests: 8,
      failed_tests: 2,
      report_type_label: "R80 Darbe Testi",
      success_rate: 80,
      localized_summaries: {
        tr: {
          summary: "Rapora göre koltuk darbe testini geçti.",
          conditions: "Sıcaklık: 23°C; Nem: %40",
          improvements: "Enerji dağıtımını iyileştirin.",
        },
        en: {
          summary: "Seat structure passed most of the impact checks.",
          conditions: "Temperature: 23C; Humidity: 40%",
          improvements: "Reinforce the left hinge.",
        },
      },
      condition_evaluation: "Test koşulları standartlara uygundu.",
      improvement_overview: "Kritik bölgelerde güçlendirme önerildi.",
      structured_sections: {
        results: {
          tr: "Ana bölme 20g altında kaldı.",
          en: "Peak load stayed within tolerance.",
        },
      },
      highlights: ["Yan hava yastığı hedeflenen sürede açıldı."],
      failures: [
        {
          test_name: "Yan Darbe",
          failure_reason: "Sensör kalibrasyonu sapma gösterdi.",
          suggested_fix: "Kalibrasyon prosedürünü güncelleyin.",
        },
      ],
      measurement_analysis: {
        overall_summary: {
          total_tests: 10,
          passed: 8,
          failed: 2,
          success_rate: 80,
        },
        measured_values: {
          peak_force: "15 kN",
        },
      },
    },
  ],
});

describe("AnalysisSummaryCard", () => {
  it("renders at least one summary entry from the AI analysis response", () => {
    const entry = createAnalysisEntry(buildSampleResponse(), { engineKey: "chatgpt" });
    expect(entry).not.toBeNull();
    render(<AnalysisSummaryCard analyses={[entry]} />);

    expect(screen.getByText("test-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("8/10 PASS · 2 FAIL")).toBeInTheDocument();
    expect(
      screen.getByText(/Analiz edilen test türü: R80 Darbe Testi/)
    ).toBeInTheDocument();
  });
});
