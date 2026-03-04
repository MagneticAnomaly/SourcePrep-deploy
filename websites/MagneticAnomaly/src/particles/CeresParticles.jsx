import React from 'react';
import { MagneticParticles } from './MagneticParticles';

export function CeresParticles(props) {
    return (
        <MagneticParticles
            {...props}
            particleCount={1800}
            planetRadius={2.0}
            rmaxRange={[5.0, 10.0]}
            baseSpeed={0.15}
            pointSize={1.5}
            cycleSpeed={0.25}
            arcBands={4}
            shellBands={4}
            tilt={[0.1, 0, 0.05]}
        />
    );
}
