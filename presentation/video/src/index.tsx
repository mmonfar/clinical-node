import { registerRoot, Composition, Series } from 'remotion';
import { TitleCard, ProblemSlide, SolutionSlide } from './NarrativeSlides';
// If these aren't in NarrativeSlides, we will need to locate them
import { TOTAL_FRAMES, FPS, S, PHASES } from './constants';

export const RemotionRoot: React.FC = () => {
    return (
        <Composition
            id="ClinicalIntelligenceNode"
            component={() => (
                <Series>
                    {/* Phase 1: Intro */}
                    <Series.Sequence durationInFrames={PHASES.TITLE.end}>
                        <TitleCard />
                    </Series.Sequence>

                    {/* Phase 2: The Problem (Safety Gaps) */}
                    <Series.Sequence durationInFrames={PHASES.PROBLEM.end - PHASES.PROBLEM.start}>
                        <ProblemSlide />
                    </Series.Sequence>

                    {/* Phase 3: The "Clinical Node" Solution */}
                    <Series.Sequence durationInFrames={PHASES.SOLUTION.end - PHASES.SOLUTION.start}>
                        <SolutionSlide />
                    </Series.Sequence>

                    {/* Phase 4: Evidence & Matrix - This is likely what feels "missing" */}
                    <Series.Sequence durationInFrames={PHASES.MATRIX.end - PHASES.MATRIX.start}>
                        {/* We need to point this to your EvidenceMatrix component */}
                        <div style={{ flex: 1, backgroundColor: '#0A1420', color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center', fontSize: 40 }}>
                            Evidence Matrix Phase
                        </div>
                    </Series.Sequence>

                    {/* Phase 5: The MDT Clash (The Roundtable) */}
                    <Series.Sequence durationInFrames={PHASES.CLASH.end - PHASES.CLASH.start}>
                        {/* This is the adversarial debate logic */}
                        <div style={{ flex: 1, backgroundColor: '#0A1420', color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center', fontSize: 40 }}>
                            MDT Roundtable Debate
                        </div>
                    </Series.Sequence>
                </Series>
            )}
            durationInFrames={TOTAL_FRAMES}
            fps={FPS}
            width={S.W}
            height={S.H}
        />
    );
};

registerRoot(RemotionRoot);