#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using Cost = long long;
constexpr Cost INF = std::numeric_limits<Cost>::max()/4;
struct Point { double lat, lon; };
struct Stop { std::string id, label; Point pos; int node=-1; double snap=0; };
struct Edge { int to; Cost seconds; };
struct Graph {
    std::map<std::string,int> ids;
    std::vector<std::string> names;
    std::vector<Point> points;
    std::vector<std::vector<Edge>> edges;
    int lookup(const std::string& key) const {
        auto it=ids.find(key);
        if(it==ids.end()) throw std::runtime_error("Unknown road node: "+key);
        return it->second;
    }
};
using Matrix=std::vector<std::vector<Cost>>;

std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start=0;
    for(std::size_t i=0;i<=line.size();i++) if(i==line.size()||line[i]=='\t'){
        fields.push_back(line.substr(start,i-start));start=i+1;
    }
    return fields;
}
template<class F> void read_tsv(const std::string& file,const std::string& header,F consume) {
    std::ifstream in(file);
    if(!in) throw std::runtime_error("Cannot open "+file);
    std::string line; int row=0;
    while(std::getline(in,line)) {
        ++row;
        if(!line.empty()&&line.back()=='\r')line.pop_back();
        if(row==1){
            if(line!=header)throw std::runtime_error(file+": unexpected header");
            continue;
        }
        if(line.empty())continue;
        try{consume(split(line));}
        catch(const std::exception& e){throw std::runtime_error(file+":"+std::to_string(row)+": "+e.what());}
    }
    if(row==0)throw std::runtime_error(file+": empty file");
}
double number(const std::string& s){
    std::size_t end=0; double v=std::stod(s,&end);
    if(end!=s.size()||!std::isfinite(v))throw std::runtime_error("Invalid number");
    return v;
}
Point point(const std::string& lat,const std::string& lon){
    Point p{number(lat),number(lon)};
    if(std::abs(p.lat)>90||std::abs(p.lon)>180)throw std::runtime_error("Coordinates out of range");
    return p;
}
double metres(Point a,Point b){
    const double r=std::acos(-1.0)/180;
    double h=std::pow(std::sin((b.lat-a.lat)*r/2),2)+
        std::cos(a.lat*r)*std::cos(b.lat*r)*std::pow(std::sin((b.lon-a.lon)*r/2),2);
    return 12742000*std::asin(std::sqrt(std::clamp(h,0.0,1.0)));
}
Graph load_graph(const std::string& nodes,const std::string& roads){
    Graph g;
    read_tsv(nodes,"id\tlatitude\tlongitude",[&](const auto& f){
        if(f.size()!=3||f[0].empty()||g.ids.count(f[0]))throw std::runtime_error("Expected unique node id and coordinates");
        if(g.names.size()>=10000)throw std::runtime_error("Maximum 10,000 road nodes");
        g.ids.emplace(f[0],static_cast<int>(g.names.size()));g.names.push_back(f[0]);
        g.points.push_back(point(f[1],f[2]));g.edges.emplace_back();
    });
    if(g.names.empty())throw std::runtime_error("No road nodes");
    int edge_count=0;
    read_tsv(roads,"from\tto\tseconds",[&](const auto& f){
        if(f.size()!=3||++edge_count>100000)throw std::runtime_error("Expected from, to and seconds; maximum 100,000 roads");
        std::size_t end=0; Cost time=std::stoll(f[2],&end);
        if(end!=f[2].size()||time<1||time>86400)throw std::runtime_error("Road time must be 1–86400 seconds");
        g.edges[g.lookup(f[0])].push_back({g.lookup(f[1]),time});
    });
    return g;
}
std::vector<Cost> dijkstra(const Graph& g,int from){
    using Item=std::pair<Cost,int>;
    std::priority_queue<Item,std::vector<Item>,std::greater<Item>> queue;
    std::vector<Cost> distance(g.names.size(),INF);
    distance[from]=0;queue.push({0,from});
    while(!queue.empty()){
        auto [cost,node]=queue.top();queue.pop();
        if(cost!=distance[node])continue;
        for(const auto& e:g.edges[node])if(cost+e.seconds<distance[e.to]){
            distance[e.to]=cost+e.seconds;queue.push({distance[e.to],e.to});
        }
    }
    return distance;
}
Cost cost(const Matrix& times,const std::vector<int>& order){
    Cost value=0;int last=0;
    for(int stop:order){value+=times[last][stop];last=stop;}
    return value+times[last][0];
}
std::vector<int> greedy(const Matrix& times){
    std::vector<int> order;std::vector<bool> used(times.size(),false);
    used[0]=true;int last=0;
    while(order.size()+1<times.size()){
        int best=-1;
        for(int j=1;j<(int)times.size();j++)
            if(!used[j]&&(best<0||times[last][j]<times[last][best]))best=j;
        order.push_back(best);used[best]=true;last=best;
    }
    return order;
}
std::vector<int> improve(const Matrix& times,std::vector<int> order){
    // Directed times: evaluate all legs after a swap, including return to depot.
    for(int pass=0;pass<12;pass++){
        Cost best=cost(times,order);int x=-1,y=-1;
        for(int i=0;i<(int)order.size();i++)for(int j=i+1;j<(int)order.size();j++){
            std::swap(order[i],order[j]);Cost c=cost(times,order);
            std::swap(order[i],order[j]);
            if(c<best){best=c;x=i;y=j;}
        }
        if(x<0)break;
        std::swap(order[x],order[y]);
    }
    return order;
}
std::vector<int> exact(const Matrix& times){
    int n=static_cast<int>(times.size())-1;if(n==0)return {};
    int states=1<<n;
    std::vector<std::vector<Cost>> dp(states,std::vector<Cost>(n,INF));
    std::vector<std::vector<int>> prev(states,std::vector<int>(n,-1));
    for(int j=0;j<n;j++)dp[1<<j][j]=times[0][j+1];
    for(int mask=1;mask<states;mask++)for(int j=0;j<n;j++)if(dp[mask][j]!=INF)
        for(int k=0;k<n;k++)if(!(mask&(1<<k))){
            int next=mask|(1<<k);Cost c=dp[mask][j]+times[j+1][k+1];
            if(c<dp[next][k]){dp[next][k]=c;prev[next][k]=j;}
        }
    int mask=states-1,last=0;
    for(int j=1;j<n;j++)if(dp[mask][j]+times[j+1][0]<dp[mask][last]+times[last+1][0])last=j;
    std::vector<int> order;
    while(last>=0){order.push_back(last+1);int before=prev[mask][last];mask^=1<<last;last=before;}
    std::reverse(order.begin(),order.end());return order;
}
std::string json(const std::string& s){
    std::ostringstream out;out<<'"';
    for(unsigned char c:s){
        if(c=='"'||c=='\\')out<<'\\'<<c;
        else if(c<32)out<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<int(c)<<std::dec;
        else out<<c;
    }
    out<<'"';return out.str();
}
void print_plan(const std::string& name,const Matrix& times,const std::vector<int>& order,const std::vector<Stop>& stops,double milliseconds){
    std::cout<<"{\"strategy\":"<<json(name)<<",\"seconds\":"<<cost(times,order)<<",\"compute_ms\":"<<milliseconds<<",\"stops\":[";
    int last=0;bool first=true;
    for(int j:order){
        const auto& s=stops[j-1];
        if(!first)std::cout<<',';
        first=false;
        std::cout<<"{\"id\":"<<json(s.id)<<",\"label\":"<<json(s.label)
                 <<",\"leg_seconds\":"<<times[last][j]<<",\"snap_metres\":"<<s.snap<<'}';
        last=j;
    }
    std::cout<<"],\"return_seconds\":"<<times[last][0]<<'}';
}
int main(int argc,char** argv){
    try{
        if(argc!=5&&argc!=6)throw std::runtime_error("Usage: route nodes.tsv roads.tsv stops.tsv depot [max-snap-metres]");
        const auto g=load_graph(argv[1],argv[2]);int depot=g.lookup(argv[4]);
        double limit=argc==6?number(argv[5]):150;
        if(limit<0||limit>10000)throw std::runtime_error("Snap limit must be 0–10000 metres");
        auto from_depot=dijkstra(g,depot);
        Graph reverse=g;reverse.edges.assign(g.edges.size(),{});
        for(int a=0;a<(int)g.edges.size();a++)for(const auto& e:g.edges[a])reverse.edges[e.to].push_back({a,e.seconds});
        auto to_depot=dijkstra(reverse,depot);
        std::vector<Stop> stops;std::vector<std::pair<std::string,std::string>> skipped;
        std::set<std::string> ids;
        read_tsv(argv[3],"id\tlabel\tlatitude\tlongitude",[&](const auto& f){
            if(f.size()!=4||f[0].empty()||f[1].empty()||!ids.insert(f[0]).second)throw std::runtime_error("Expected unique stop id, label and coordinates");
            if(ids.size()>100)throw std::runtime_error("Maximum 100 stops per route");
            Stop s{f[0],f[1],point(f[2],f[3])}; s.snap=limit+1;
            for(int i=0;i<(int)g.points.size();i++){
                double d=metres(s.pos,g.points[i]);
                if(d<s.snap){s.node=i;s.snap=d;}
            }
            if(s.node<0||s.snap>limit)skipped.push_back({s.id,"No road node within snap limit"});
            else if(from_depot[s.node]==INF||to_depot[s.node]==INF)skipped.push_back({s.id,"No round trip to depot"});
            else stops.push_back(s);
        });
        std::vector<int> nodes{depot};for(const auto& s:stops)nodes.push_back(s.node);
        Matrix times(nodes.size(),std::vector<Cost>(nodes.size(),0));
        for(std::size_t i=0;i<nodes.size();i++){
            auto distance=dijkstra(g,nodes[i]);
            for(std::size_t j=0;j<nodes.size();j++)times[i][j]=distance[nodes[j]];
        }
        using Clock=std::chrono::steady_clock;
        auto begin=Clock::now();
        auto baseline=greedy(times);
        auto elapsed=[&](){return std::chrono::duration<double,std::milli>(Clock::now()-begin).count();};
        double baseline_ms=elapsed();begin=Clock::now();
        bool optimal=stops.size()<=12;
        auto best=optimal?exact(times):improve(times,baseline);
        double best_ms=elapsed();
        std::cout<<"{\"schema\":1,\"depot\":"<<json(argv[4])<<",\"requested\":"<<ids.size()
                 <<",\"optimal_for_served_stops\":"<<(optimal?"true":"false")<<",\"plans\":[";
        print_plan("Nearest neighbour",times,baseline,stops,baseline_ms);std::cout<<',';
        print_plan(optimal?"Held–Karp exact":"Nearest neighbour + swaps",times,best,stops,best_ms);
        std::cout<<"],\"unrouted\":[";
        for(std::size_t i=0;i<skipped.size();i++){
            if(i)std::cout<<',';
            std::cout<<"{\"id\":"<<json(skipped[i].first)<<",\"reason\":"<<json(skipped[i].second)<<'}';
        }
        std::cout<<"]}\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
