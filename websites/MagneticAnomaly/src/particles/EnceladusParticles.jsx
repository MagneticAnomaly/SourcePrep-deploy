import React from 'react';
import { MagneticParticles } from './MagneticParticles';

export function EnceladusParticles(props) {
    return (
        <MagneticParticles
            {...props}
            particleCount={4200}
            planetRadius={1.5}
            rmaxRange={[3.5, 7.0]}
            baseSpeed={0.3}
            pointSize={0.5}
            cycleSpeed={0.035}
            arcBands={4}
            shellBands={7}
            tilt={[0, 0, 0]}
        />
    );
}
