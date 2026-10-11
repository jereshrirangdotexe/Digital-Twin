def raw_score(artifact,features):
    if artifact['kind']=='physics':return min(1.,max(0.,features[1]/20))
    return float(artifact['estimator'].predict_proba([features])[0,1])
class Decision:
    def __init__(self,artifact):self.artifact=artifact;self.since=None
    def update(self,score,dt,eligible):
        threshold=self.artifact['threshold']
        if not eligible or score is None or score<threshold:self.since=None;return False
        if self.since is None:self.since=dt
        return (dt-self.since).total_seconds()/60>=15
